"""容器序列化、项目分类、自保护与冲突检测。

**规则全在本文件一处**：API 层只负责编排，不自己判项目、不自己判保护。
分类是「实时容器 × 落库规则」的纯函数 —— 容器清单不落库，规则落库。
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.timeutil import to_naive_local
from app.modules.agent.agent_config import agent_settings

# Docker 日志行首时间戳：2026-10-16T11:22:33.123456789Z
_LOG_TS = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)(?P<rest>\s.*)$")


@dataclass(frozen=True)
class Classification:
    """一个容器的项目归属判定结果。"""
    project_key: str | None = None
    project_name: str | None = None
    # compose / name / none / conflict
    matched_by: str = "none"
    rule_id: int | None = None
    conflict: bool = False
    # 冲突时列出所有命中规则的 project_key
    candidates: list[str] = field(default_factory=list)


def _as_list(value: object) -> list[str]:
    """把 JSON 列读出来的值规整成非空字符串列表（列可能是 None / 单值 / 混杂）。"""
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def classify_container(labels: dict, name: str, image: str, rules: list) -> Classification:
    """把容器归到唯一一个项目；归属不明一律不指派。

    判定顺序：
      1. 只取 enabled 规则
      2. 一级（compose）：label `com.docker.compose.project` 精确命中 compose_project_names
      3. 二级（容器名）：**仅当一级为空时**，用 re.search(pattern, name, re.I)

    命中 0 条 → none（未分类）；命中 1 条 → 采用；**命中 ≥2 条 → conflict，不指派**。

    冲突时**刻意不按 priority 自动挑一条**：文档明写「规则冲突时应标记为待处理，
    避免错误归类」，自动指派只会把配置错误藏起来。priority 仅在 UI 上作为
    「先看哪条」的提示展示。

    `image` 目前不参与判定，保留在签名里是为了将来加「按镜像名分类」时不用改所有调用点。

    边界：正则之间的重叠是**不可判定**的，所以本函数只做「多个规则同时命中同一个
    容器」这一层检测，不做规则两两之间的正则包含分析 —— 后者会给出大量假阳性。
    真正的重叠配置由 `detect_rule_conflicts()` 在显式重复项上提示。
    """
    enabled = [r for r in rules if getattr(r, "enabled", True)]
    if not enabled:
        return Classification()

    compose_project = str(labels.get("com.docker.compose.project") or "").strip()
    if compose_project:
        hits = [r for r in enabled if compose_project in _as_list(r.compose_project_names)]
        if len(hits) == 1:
            rule = hits[0]
            return Classification(rule.project_key, rule.project_name, "compose", rule.id)
        if len(hits) > 1:
            return Classification(matched_by="conflict", conflict=True,
                                  candidates=sorted({r.project_key for r in hits}))

    hits = []
    for rule in enabled:
        for pattern in _as_list(rule.container_name_patterns):
            try:
                if re.search(pattern, name or "", re.IGNORECASE):
                    hits.append(rule)
                    break
            except re.error:
                # 非法正则在保存时已被 schemas 校验拦下；这里兜住历史脏数据，
                # 让个别坏规则不影响其余规则的判定。
                continue
    if len(hits) == 1:
        rule = hits[0]
        return Classification(rule.project_key, rule.project_name, "name", rule.id)
    if len(hits) > 1:
        return Classification(matched_by="conflict", conflict=True,
                              candidates=sorted({r.project_key for r in hits}))
    return Classification()


def detect_rule_conflicts(rules: list) -> list[dict]:
    """找出规则之间**显式**的重复声明，供「项目与分类规则」页顶部告警。

    只检测两种确定无歧义的情况：
      - 同一个 compose 项目名被 ≥2 条启用规则声明
      - 同一段容器名正则字面量出现在 ≥2 条启用规则里

    不做正则语义重叠分析（不可判定，且假阳性高）。
    """
    conflicts: list[dict] = []
    enabled = [r for r in rules if getattr(r, "enabled", True)]

    by_compose: dict[str, list[str]] = {}
    by_pattern: dict[str, list[str]] = {}
    for rule in enabled:
        for item in _as_list(rule.compose_project_names):
            by_compose.setdefault(item, []).append(rule.project_key)
        for item in _as_list(rule.container_name_patterns):
            by_pattern.setdefault(item, []).append(rule.project_key)

    for source, bucket in (("compose_project_names", by_compose), ("container_name_patterns", by_pattern)):
        for value, keys in bucket.items():
            unique = sorted(set(keys))
            if len(unique) > 1:
                conflicts.append({"field": source, "value": value, "project_keys": unique})
    return conflicts


def is_protected(labels: dict, name: str) -> tuple[bool, str | None]:
    """平台自身容器禁止任何生命周期操作。

    两条规则都**无需人工打标**：compose 会自动打上项目 / 服务标签。
    """
    if str(labels.get("platform.protected") or "").strip().lower() == "true":
        return True, "容器标记了 platform.protected=true"
    project = str(labels.get("com.docker.compose.project") or "").strip()
    if project and project == agent_settings.agent_protected_project:
        service = str(labels.get("com.docker.compose.service") or "").strip() or name
        return True, f"平台自身服务（compose 项目 {project} / 服务 {service}）"
    return False, None


def refusal_reason(container: dict, *, registered: bool = False) -> str | None:
    """返回拒绝操作的原因；None 表示可操作。前端与 409 判定共用这一处规则。

    - **自保护永远最先判定**：即使容器已登记到某个智能体，平台自身容器仍拒绝；
    - `registered=True`（容器名已登记在智能体台账）：放行，不再受项目分类门禁约束。
      智能体管理的口径是「我登记的容器归我管」，分类规则是为未登记容器提供的
      自动归属机制，不该反过来卡住显式登记；
    - 未登记容器保持原有收窄：**分类未落到唯一项目（未分类 / 冲突）一律只读**。
    """
    if container["protected"]:
        return f"平台自身容器受保护，禁止该操作（{container['protected_reason']}）"
    if registered:
        return None
    if container["conflict"]:
        candidates = "、".join(container.get("candidates") or [])
        return f"分类规则冲突（同时命中 {candidates}），请先解决规则冲突，当前只读"
    if not container["project_key"]:
        return "未分类到任何项目，未分类容器只读（可在「项目与分类规则」中配置规则，或在「智能体管理」中登记该容器）"
    return None


def _short_id(container_id: str) -> str:
    return (container_id or "")[:12]


def _local_iso(epoch: int | None) -> str | None:
    """Docker 的 Created 是 epoch UTC，必须归一为 naive 北京时。"""
    if not epoch:
        return None
    moment = to_naive_local(datetime.fromtimestamp(epoch, tz=timezone.utc))
    return moment.isoformat() if moment else None


def parse_docker_time(value: str | None) -> str | None:
    """Docker 的 RFC3339 UTC 时间串 → naive 北京时 ISO 串。"""
    if not value or value.startswith("0001-01-01"):  # Docker 的零值
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    converted = to_naive_local(moment)
    return converted.isoformat() if converted else None


def _format_ports(ports: list) -> list[str]:
    formatted: list[str] = []
    for item in ports or []:
        if not isinstance(item, dict):
            continue
        private = item.get("PrivatePort")
        public = item.get("PublicPort")
        protocol = item.get("Type") or "tcp"
        if public:
            formatted.append(f"{item.get('IP') or '0.0.0.0'}:{public}->{private}/{protocol}")
        else:
            formatted.append(f"{private}/{protocol}")
    return formatted


def serialize_container(raw: dict, rules: list | None = None) -> dict:
    """把 /containers/json 的一项转成前端契约，并附上项目归属。"""
    labels = raw.get("Labels") or {}
    names = raw.get("Names") or []
    name = str(names[0]).lstrip("/") if names else ""
    image = raw.get("Image") or ""
    container_id = raw.get("Id") or ""
    protected, reason = is_protected(labels, name)
    classification = classify_container(labels, name, image, rules or [])
    return {
        "container_id": _short_id(container_id),
        "full_id": container_id,
        "name": name,
        "image": image,
        "image_id": _short_id(raw.get("ImageID") or ""),
        "state": raw.get("State") or "unknown",
        "status": raw.get("Status") or "",
        "protected": protected,
        "protected_reason": reason,
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_service": labels.get("com.docker.compose.service"),
        "ports": _format_ports(raw.get("Ports") or []),
        "created_at": _local_iso(raw.get("Created")),
        "project_key": classification.project_key,
        "project_name": classification.project_name,
        "matched_by": classification.matched_by,
        "conflict": classification.conflict,
        "candidates": classification.candidates,
    }


def load_rules(db) -> list:
    """取全部分类规则（含停用的，供规则页展示）。"""
    from sqlalchemy import select

    from app.modules.agent.models import AgentProjectRule

    return list(db.scalars(select(AgentProjectRule)).all())


def list_serialized_containers(db) -> list[dict]:
    """实时容器列表 + 分类（供各处复用，避免每个接口各写一遍）。"""
    from app.modules.agent import docker_client

    rules = load_rules(db)
    return [serialize_container(raw, rules) for raw in docker_client.list_containers()]


def project_summary(rules: list, containers: list[dict]) -> dict:
    """按项目分组统计，另给出 unclassified / conflict 两个桶。"""
    buckets: dict[str, dict] = {}
    for rule in rules:
        buckets[rule.project_key] = {
            "project_key": rule.project_key,
            "project_name": rule.project_name,
            "enabled": bool(getattr(rule, "enabled", True)),
            "rule_id": getattr(rule, "id", None),
            "total": 0,
            "running": 0,
            "stopped": 0,
        }
    unclassified = {"key": "unclassified", "name": "未分类", "total": 0, "running": 0, "stopped": 0}
    conflict = {"key": "conflict", "name": "规则冲突", "total": 0, "running": 0, "stopped": 0}

    for container in containers:
        running = container["state"] == "running"
        if container["conflict"]:
            target = conflict
        elif container["project_key"] and container["project_key"] in buckets:
            target = buckets[container["project_key"]]
        elif container["project_key"]:
            # 规则已被删掉，但容器还带着旧的分类缓存值（正常不会发生，兜底）
            target = unclassified
        else:
            target = unclassified
        target["total"] += 1
        target["running" if running else "stopped"] += 1

    return {
        "projects": sorted(buckets.values(), key=lambda item: item["project_key"]),
        "unclassified": unclassified,
        "conflict": conflict,
    }


def localize_log_timestamps(text: str) -> str:
    """把 Docker 日志行首的 RFC3339 **UTC** 时间戳转成 naive 北京时。

    平台约定「全库时间存 naive 本地时间」。Docker 的 `timestamps=1` 会给 UTC，
    直接透出就破约；逐行转换后输出仍完全落在约定内。

    小数位截到 6 位：Docker 是纳秒，`fromisoformat` 在微秒上最稳。
    不匹配的行（连续输出、非时间戳开头）原样放行。
    """
    if not text:
        return text
    out: list[str] = []
    for line in text.splitlines():
        match = _LOG_TS.match(line)
        if not match:
            out.append(line)
            continue
        raw_ts = match.group("ts")
        head, _, frac = raw_ts[:-1].partition(".")
        frac = (frac + "000000")[:6] if frac else "000000"
        try:
            moment = datetime.fromisoformat(f"{head}+00:00")
        except ValueError:
            out.append(line)
            continue
        local = to_naive_local(moment)
        if local is None:
            out.append(line)
            continue
        out.append(f"{local.strftime('%Y-%m-%d %H:%M:%S')}.{frac}{match.group('rest')}")
    return "\n".join(out)


def build_exec_commands(container: dict) -> dict:
    """生成宿主机上执行的命令文本（平台刻意不提供 Web 终端 / exec 接口）。

    与文档「不允许前端直接执行 Shell 命令」一致：只给文本，不给执行通道。
    """
    short_id = container["container_id"]
    return {
        "container_id": short_id,
        "full_id": container["full_id"],
        "shell": "sh",
        "command": f"docker exec -it {short_id} sh",
        "fallback_command": f"docker exec -it {short_id} bash",
        "host_note": "请在运行 Docker 的主机上执行本命令（平台容器内没有 docker CLI）。",
    }
