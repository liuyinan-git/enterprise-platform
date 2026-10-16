"""容器识别、自保护、序列化，以及「台账 ↔ 容器」的关联规则。

规则集中在本文件一处，API 层只负责编排。
"""

import re
from datetime import datetime, timezone

from app.core.timeutil import to_naive_local
from app.modules.database.container_config import container_settings

# 只有这些类型开放生命周期操作，其余一律只读。
#
# 加一个新的受管类型 = 在下面三张表里各加一行（别名 / 镜像名 / 容器名），别处不用动。
# 判定顺序是 label → 镜像名 → 容器名，越靠后越不确定，所以：
#   - 镜像名用「整段匹配」（要求 mysql 后面紧接 : - @ 或字符串结束），
#     这样 mysql-backup 之类的工具镜像不会被误判成数据库；
#   - 容器名只收窄到毫无歧义的写法（pg 要求前面是分隔符，避免误伤 ppg）；
#   - 镜像名 / 容器名推断出来的结果，最后还要过一道应用层判据 `_is_app_tier`
#     （后端 / 前端 / UI / MCP 这类不是数据存储，见下面 _APP_TIER_TOKENS 的说明）。
#     label 声明不受这道判据约束。
MANAGED_TYPES = (
    # 关系型
    "postgres", "mysql", "mariadb", "oracle", "sqlserver",
    # 缓存 / 文档 / 图 / 宽列
    "redis", "memcached", "mongodb", "cassandra", "neo4j",
    # 搜索 / 分析 / 时序
    "elasticsearch", "clickhouse", "influxdb",
    # 向量库
    "milvus", "qdrant", "weaviate", "chroma",
    # 知识库（本身不是数据库，但同属本平台的纳管对象）
    "weknora", "cognee",
)

_TYPE_ALIASES = {
    "postgres": "postgres", "postgresql": "postgres", "pgsql": "postgres", "pg": "postgres",
    "mysql": "mysql",
    "mariadb": "mariadb", "maria": "mariadb",
    "oracle": "oracle", "oracledb": "oracle",
    "sqlserver": "sqlserver", "mssql": "sqlserver", "sql-server": "sqlserver",
    "redis": "redis", "keydb": "redis", "valkey": "redis",
    "memcached": "memcached", "memcache": "memcached",
    "mongodb": "mongodb", "mongo": "mongodb",
    "cassandra": "cassandra", "scylla": "cassandra", "scylladb": "cassandra",
    "neo4j": "neo4j",
    "elasticsearch": "elasticsearch", "elastic": "elasticsearch", "opensearch": "elasticsearch",
    "clickhouse": "clickhouse",
    "influxdb": "influxdb", "influx": "influxdb",
    "milvus": "milvus",
    "qdrant": "qdrant",
    "weaviate": "weaviate",
    "chroma": "chroma", "chromadb": "chroma",
    "weknora": "weknora",
    "cognee": "cognee",
}


def _image_pattern(
    *names: str, prefix: str = r"[/:]", suffix: str = r"[:@/]"
) -> re.Pattern[str]:
    """按「路径段整段」匹配镜像名，兼容 bitnami/postgresql:16 这类带 registry / namespace 的引用。

    prefix / suffix 是这个名字前后允许出现的字符，两边都**刻意不放行 `-`**：
    放行就会把 `mysql-backup-tool`、`mysql-exporter` 这类工具镜像判成数据库。
    `-` 只对确实存在的名字（oracle-xe）单独写进备选里。

    suffix 允许 `/` 是为了 mcr.microsoft.com/mssql/server 这种名字后面还有路径段的；
    oracle 官方镜像在 container-registry.oracle.com 下，所以它额外放行 `.`。
    """
    joined = "|".join(names)
    return re.compile(rf"(^|{prefix})(?:{joined})({suffix}|$)", re.IGNORECASE)


# 镜像名回退
_IMAGE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("postgres", _image_pattern("postgres", "postgresql", "paradedb", "pgvector", "timescaledb", "timescale")),
    ("mysql", _image_pattern("mysql", "percona")),
    ("mariadb", _image_pattern("mariadb")),
    # 两侧都放行 `.`，否则 container-registry.oracle.com/... 匹配不上；
    # 又因为要求 oracle 后面紧接分隔符，oraclelinux 这类基础镜像不会被误伤。
    ("oracle", _image_pattern("oracle", "oracledb", "oracle-xe", "oracle-free",
                              prefix=r"[/:.]", suffix=r"[:@/.]")),
    ("sqlserver", _image_pattern("mssql", "sqlserver")),
    ("redis", _image_pattern("redis", "keydb", "valkey")),
    ("memcached", _image_pattern("memcached")),
    ("mongodb", _image_pattern("mongo", "mongodb")),
    ("cassandra", _image_pattern("cassandra", "scylla")),
    ("neo4j", _image_pattern("neo4j")),
    ("elasticsearch", _image_pattern("elasticsearch", "opensearch")),
    ("clickhouse", _image_pattern("clickhouse")),
    ("influxdb", _image_pattern("influxdb")),
    ("milvus", _image_pattern("milvus")),
    ("qdrant", _image_pattern("qdrant")),
    ("weaviate", _image_pattern("weaviate")),
    ("chroma", _image_pattern("chroma", "chromadb")),
    # 这两个是品牌名而非仓库段，用子串匹配（wechatopenai/weknora-app 这类）。
    # 子串匹配必然过宽，所以这两个（以及所有推断结果）都要再经 `_guarded` 的应用层判据。
    ("weknora", re.compile(r"weknora", re.IGNORECASE)),
    ("cognee", re.compile(r"cognee", re.IGNORECASE)),
)

# 容器名兜底：比镜像名更窄，只收毫无歧义的写法
_NAME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("postgres", re.compile(r"(^|[-_])pg([-_]|\d|$)|postgres", re.IGNORECASE)),
    ("mysql", re.compile(r"(^|[-_])mysql([-_]|\d|$)", re.IGNORECASE)),
    ("mariadb", re.compile(r"(^|[-_])mariadb([-_]|\d|$)", re.IGNORECASE)),
    ("oracle", re.compile(r"(^|[-_])oracle([-_]|\d|$)", re.IGNORECASE)),
    ("sqlserver", re.compile(r"(^|[-_])(mssql|sqlserver)([-_]|\d|$)", re.IGNORECASE)),
    ("redis", re.compile(r"redis", re.IGNORECASE)),
    ("memcached", re.compile(r"memcached", re.IGNORECASE)),
    ("mongodb", re.compile(r"(^|[-_])mongo(db)?([-_]|\d|$)", re.IGNORECASE)),
    ("cassandra", re.compile(r"cassandra", re.IGNORECASE)),
    ("neo4j", re.compile(r"neo4j", re.IGNORECASE)),
    ("elasticsearch", re.compile(r"elasticsearch|opensearch", re.IGNORECASE)),
    ("clickhouse", re.compile(r"clickhouse", re.IGNORECASE)),
    ("influxdb", re.compile(r"influxdb", re.IGNORECASE)),
    ("milvus", re.compile(r"milvus", re.IGNORECASE)),
    ("qdrant", re.compile(r"qdrant", re.IGNORECASE)),
    ("weaviate", re.compile(r"weaviate", re.IGNORECASE)),
    ("chroma", re.compile(r"(^|[-_])chroma(db)?([-_]|\d|$)", re.IGNORECASE)),
    ("weknora", re.compile(r"weknora", re.IGNORECASE)),
    ("cognee", re.compile(r"cognee", re.IGNORECASE)),
)


# 应用层容器（后端 / 前端 / UI / MCP / 边车…）不是数据存储，一律不纳入受管类型。
#
# 为什么需要这一层：`weknora` / `cognee` 是**品牌名**而不是仓库段，只能子串匹配，
# 而同一个品牌下既有知识库本体、也有业务方自己起的应用容器，光看品牌名分不开。
# 本机实测的 11 个命中全部是应用层：
#   weknora-business-backend / weknora-business-frontend / wechatopenai/weknora-app /
#   wechatopenai/weknora-ui / wechatopenai/weknora-docreader / weknora-rerank（镜像是 llama.cpp，
#   只有容器名带 weknora）/ cognee-backend / cognee-mcp / cognee-cognee / cognee/cognee-ui /
#   cognee-frontend
# 它们对应的真数据存储（WeKnora-postgres → paradedb、cognee-src-postgres → pgvector、
# 各自的 redis）本来就已经按镜像名正确识别成 postgres / redis 了，品牌名不提供任何额外信号。
#
# 判据因此从「叫什么品牌」换成「这一层是应用还是数据存储」：镜像名 + 容器名切词后
# 只要命中下面任一个，就认定是应用层，归为未分类（只读，且 `managed_type_source="app"`）。
#
# 刻意**不收** `server`：mcr.microsoft.com/mssql/server 的末段就是 server，收了会误伤 SQL Server；
# 同理不收 `registry` / `database`，oracle 官方镜像路径里就有。
#
# 想强行纳管某个应用容器（例如就要管 WeKnora 本体），给它打 `platform.type` 标签即可——
# label 是人工显式声明、优先级最高，**不受本判据约束**。
_APP_TIER_TOKENS = frozenset({
    "app", "backend", "frontend", "ui", "web", "webui", "api", "mcp",
    "worker", "beat", "gateway", "proxy", "nginx", "exporter",
    "docreader", "rerank", "studio", "sandbox", "console", "dashboard", "admin",
})

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _is_app_tier(image: str, name: str) -> bool:
    """镜像名 + 容器名一起切词判断是否应用层。

    两边都要看：`cognee-src-backend` 的镜像是 `cognee-cognee:latest`（自己看不出是应用），
    而 `biz-backend` 的镜像 `weknora-business-backend` 又只有镜像能看出来。
    """
    tokens = set(_TOKEN_SPLIT.split(f"{image or ''} {name or ''}".lower()))
    return bool(tokens & _APP_TIER_TOKENS)


def _guarded(managed_type: str, source: str, image: str, name: str) -> tuple[str, str]:
    """推断出的类型先过应用层判据；命中则降级为未分类，并留下 source="app" 说明原因。"""
    if _is_app_tier(image, name):
        return "unknown", "app"
    return managed_type, source


def classify_container(labels: dict, image: str, name: str) -> tuple[str, str]:
    """label 优先，镜像名回退，容器名兜底；都不中返回 ("unknown", "none")。

    label 是人工显式声明，不受应用层判据约束；推断出的结果才需要过 `_guarded`。
    """
    declared = str(labels.get("platform.type") or "").strip().lower()
    if declared:
        mapped = _TYPE_ALIASES.get(declared)
        if mapped:
            return mapped, "label"
    for managed_type, pattern in _IMAGE_PATTERNS:
        if pattern.search(image or ""):
            return _guarded(managed_type, "image", image, name)
    for managed_type, pattern in _NAME_PATTERNS:
        if pattern.search(name or ""):
            return _guarded(managed_type, "name", image, name)
    return "unknown", "none"


def is_protected(labels: dict, name: str) -> tuple[bool, str | None]:
    """平台自身容器禁止任何生命周期操作。

    两条规则都**无需人工打标**：compose 会自动打上项目 / 服务标签。
    """
    if str(labels.get("platform.protected") or "").strip().lower() == "true":
        return True, "容器标记了 platform.protected=true"
    project = str(labels.get("com.docker.compose.project") or "").strip()
    if project and project == container_settings.container_protected_project:
        service = str(labels.get("com.docker.compose.service") or "").strip() or name
        return True, f"平台自身服务（compose 项目 {project} / 服务 {service}）"
    return False, None


def refusal_reason(container: dict) -> str | None:
    """返回拒绝操作的原因；None 表示可操作。前端与 409 判定共用这一处规则。"""
    if container["protected"]:
        return f"平台自身容器受保护，禁止该操作（{container['protected_reason']}）"
    if container["managed_type"] == "unknown":
        if container.get("managed_type_source") == "app":
            return "识别为应用层容器（后端 / 前端 / UI 等），不是数据存储，只读"
        return f"未识别为受管类型（当前纳管 {len(MANAGED_TYPES)} 类），只读"
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


def serialize_container(raw: dict) -> dict:
    """把 /containers/json 的一项转成前端契约。"""
    labels = raw.get("Labels") or {}
    names = raw.get("Names") or []
    name = str(names[0]).lstrip("/") if names else ""
    image = raw.get("Image") or ""
    managed_type, source = classify_container(labels, image, name)
    protected, reason = is_protected(labels, name)
    container_id = raw.get("Id") or ""
    return {
        "container_id": _short_id(container_id),
        "full_id": container_id,
        "name": name,
        "image": image,
        "image_id": _short_id(raw.get("ImageID") or ""),
        "managed_type": managed_type,
        "managed_type_source": source,
        "state": raw.get("State") or "unknown",
        "status": raw.get("Status") or "",
        "protected": protected,
        "protected_reason": reason,
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_service": labels.get("com.docker.compose.service"),
        "ports": _format_ports(raw.get("Ports") or []),
        "created_at": _local_iso(raw.get("Created")),
    }


def normalize_name(value: str | None) -> str:
    """把 instance_code / 容器名归一，便于跨命名风格匹配。"""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def build_container_index(containers: list[dict]) -> dict[str, dict[str, dict]]:
    """建立 full_id / 短 ID / 归一容器名 三个索引。"""
    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for container in containers:
        full_id = container.get("full_id") or ""
        if full_id:
            by_id[full_id] = container
            by_id[full_id[:12]] = container
        key = normalize_name(container.get("name"))
        if key:
            by_name.setdefault(key, container)
    return {"by_id": by_id, "by_name": by_name}


def resolve_instance_container(
    instance_code: str, attributes: object, index: dict[str, dict[str, dict]]
) -> tuple[dict | None, str]:
    """台账行 → 容器。

    优先 `attributes` 里显式登记的引用（`database_instance.attributes` 是既有 JSON 列，
    直接利用），其次 `instance_code` 归一后与容器名同名。
    """
    attrs = attributes if isinstance(attributes, dict) else {}
    for key in ("docker_container_id", "docker_container"):
        reference = attrs.get(key)
        if isinstance(reference, str) and reference.strip():
            token = reference.strip()
            hit = (
                index["by_id"].get(token)
                or index["by_id"].get(token[:12])
                or index["by_name"].get(normalize_name(token))
            )
            if hit:
                return hit, f"attributes.{key}"
    hit = index["by_name"].get(normalize_name(instance_code))
    if hit:
        return hit, "instance_code"
    return None, "none"


def build_exec_commands(container: dict) -> dict:
    """生成宿主机上执行的命令文本（平台刻意不提供 Web 终端）。

    主命令一律给 `sh`：受管类型覆盖 19 种镜像，其中不少常见 tag 是 alpine（没有 bash），
    而 `/bin/sh` 在上述所有镜像里都存在。bash 作为 fallback 一并返回，想要更顺手的
    交互（readline / history）就换它。这里刻意不按类型区分——按类型维护一份
    「哪些镜像带 bash」的清单只会随着镜像更新而腐坏。
    """
    shell, fallback = "sh", "bash"
    short_id = container["container_id"]
    return {
        "container_id": short_id,
        "full_id": container["full_id"],
        "shell": shell,
        "command": f"docker exec -it {short_id} {shell}",
        "fallback_command": f"docker exec -it {short_id} {fallback}",
        "host_note": "请在运行 Docker 的主机上执行本命令（平台容器内没有 docker CLI）。",
    }
