"""容器实况接口：列表 / 发现 / 详情 / 日志 / 启停重启 / 操作审计。

**读写守卫分离**：本文件里的读接口由父 router（`api.py`）的
`require_permission("agent:view")` 覆盖；三个写接口**逐路由**要求
`require_permission("agent:container")`。

权限由 RBAC 统一解析：网关注入的角色 ID 映射成平台角色码，再求出权限集；
`agent:container` 与台账写 `agent:manage` 刻意分离，可分别授予。网关认证关闭时
仍是匿名 admin（角色 admin 恒放行）。

注意：本 router **不带 prefix**，它被 `api.py` 的父 router（`prefix="/api/v1"`）include，
因此这里的 "/agent/containers" 实际暴露为 "/api/v1/agent/containers"。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user, require_permission
from app.core.db import get_db
from app.core.response import ok, paginated
from app.core.timeutil import local_now
from app.modules.agent import containers as container_rules
from app.modules.agent import docker_client
from app.modules.agent.models import AgentContainerAudit, AgentRegistry
from app.modules.agent.schemas import ContainerActionIn
from app.modules.agent.services import record_container_audit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent-platform"])


def _live_containers(db: Session) -> list[dict]:
    """实况容器列表；Docker 不可达时抛 503（读列表的接口另行降级为 200）。"""
    try:
        return container_rules.list_serialized_containers(db)
    except docker_client.DockerUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Docker 服务不可达：{exc}") from exc


def _match(containers: list[dict], container_id: str) -> dict | None:
    """按 full ID / 12 位短 ID / 容器名定位。"""
    token = (container_id or "").strip()
    for item in containers:
        if token and token in (item["full_id"], item["container_id"], item["name"]):
            return item
    return None


def _registered_names(db: Session) -> set[str]:
    """已登记智能体绑定的容器名集合（一次查询，供启停放行判定）。"""
    rows = db.scalars(
        select(AgentRegistry.container_name).where(AgentRegistry.container_name.is_not(None))
    ).all()
    return {name for name in rows if name}


def _record(db: Session, target: dict, action: str, result: str, user: CurrentUser, detail: dict) -> None:
    """写审计。

    **审计写失败绝不能把成功的操作变成 500**，所以这里单独兜住异常。

    `user.username`（x-user-num）可能变，真正的稳定标识是 `user_id`；角色快照用于
    回答「他当时凭什么权限操作」。两者都塞进 detail 的 JSON，无需改表。
    """
    payload = dict(detail or {})
    payload["user_id"] = user.user_id
    payload["roles"] = sorted(user.roles)
    payload["permissions"] = sorted(user.permissions)
    try:
        record_container_audit(
            db,
            container_id=target["container_id"],
            container_name=target["name"],
            project_key=target.get("project_key"),
            action=action,
            result=result,
            operator=user.username,
            detail=payload,
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("写入容器操作审计失败 container=%s action=%s", target.get("container_id"), action)


def _require_reason(payload: ContainerActionIn | None) -> str:
    """停止 / 重启必须填写原因；启动不要求。

    原因随审计落库，回答「为什么停」——这是事后追责里最容易缺失的一环。
    """
    reason = (payload.reason or "").strip() if payload else ""
    if not reason:
        raise HTTPException(status_code=422, detail="请填写操作原因")
    return reason


def _operate(
    container_id: str,
    action: str,
    timeout: int | None,
    user: CurrentUser,
    db: Session,
    operator_reason: str | None = None,
) -> dict:
    live = _live_containers(db)
    target = _match(live, container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")

    refusal = container_rules.refusal_reason(target, registered=target["name"] in _registered_names(db))
    if refusal:
        # 受保护 / 未分类 / 规则冲突 → **在调用 Docker 之前**就拒绝，并留痕
        _record(db, target, action, "refused", user, {"reason": refusal, "operator_reason": operator_reason})
        raise HTTPException(status_code=409, detail=refusal)

    try:
        if action == "start":
            docker_client.start_container(target["full_id"])
        elif action == "stop":
            docker_client.stop_container(target["full_id"], timeout)
        else:
            docker_client.restart_container(target["full_id"], timeout)
    except docker_client.ContainerNotFound as exc:
        _record(db, target, action, "failed", user, {"error": str(exc), "operator_reason": operator_reason})
        raise HTTPException(status_code=404, detail="容器不存在") from exc
    except docker_client.DockerUnavailable as exc:
        _record(db, target, action, "failed", user, {"error": str(exc), "operator_reason": operator_reason})
        raise HTTPException(status_code=503, detail=f"操作失败：{exc}") from exc

    _record(db, target, action, "success", user, {
        "timeout": timeout,
        "project_key": target.get("project_key"),
        "operator_reason": operator_reason,
    })
    return {
        "container_id": target["container_id"],
        "name": target["name"],
        "action": action,
        "result": "success",
    }


@router.get("/agent/containers")
def list_containers(
    project_key: str | None = Query(default=None, description="项目 key；unclassified / conflict 为两个特殊桶"),
    state: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_protected: bool = Query(default=True),
    include_stopped: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """扁平容器列表。Docker 不可达时**仍返回 200 + degraded**，由页面显示告警条。"""
    try:
        items = container_rules.list_serialized_containers(db)
    except docker_client.DockerUnavailable as exc:
        return ok({
            "items": [],
            "total": 0,
            "summary": None,
            "degraded": True,
            "error": str(exc),
            "generated_at": local_now().isoformat(),
        })

    summary = container_rules.project_summary(container_rules.load_rules(db), items)

    if project_key == "unclassified":
        items = [c for c in items if not c["project_key"] and not c["conflict"]]
    elif project_key == "conflict":
        items = [c for c in items if c["conflict"]]
    elif project_key:
        items = [c for c in items if c["project_key"] == project_key]
    if state:
        items = [c for c in items if c["state"] == state]
    if not include_stopped and not state:
        items = [c for c in items if c["state"] == "running"]
    if q:
        keyword = q.strip().lower()
        items = [c for c in items if keyword in c["name"].lower() or keyword in c["image"].lower()]
    if not include_protected:
        items = [c for c in items if not c["protected"]]

    return ok({
        "items": items,
        "total": len(items),
        "summary": summary,
        "degraded": False,
        "error": None,
        "generated_at": local_now().isoformat(),
    })


@router.post("/agent/containers/discover")
def discover_containers(db: Session = Depends(get_db)):
    """重新发现并分类：返回各类计数，供「重新发现」按钮回显。

    容器清单本身不落库，所以这里**不写任何数据**，只是把实时分类结果汇个总。
    """
    try:
        items = container_rules.list_serialized_containers(db)
    except docker_client.DockerUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Docker 服务不可达：{exc}") from exc

    summary = container_rules.project_summary(container_rules.load_rules(db), items)
    classified = sum(p["total"] for p in summary["projects"])
    return ok({
        "discovered": len(items),
        "classified": classified,
        "unclassified": summary["unclassified"]["total"],
        "conflict": summary["conflict"]["total"],
        "project_count": sum(1 for p in summary["projects"] if p["total"] > 0),
        "generated_at": local_now().isoformat(),
    })


@router.get("/agent/containers/{container_id}")
def get_container(container_id: str, db: Session = Depends(get_db)):
    target = _match(_live_containers(db), container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")

    payload: dict = {"container": target, "detail": None, "exec_command": None}
    try:
        raw = docker_client.inspect_container(target["full_id"])
    except docker_client.DockerUnavailable:
        return ok(payload)  # 详情属增强信息，拿不到就只回摘要
    except docker_client.ContainerNotFound:
        raise HTTPException(status_code=404, detail="容器不存在") from None

    state = raw.get("State") or {}
    networks = ((raw.get("NetworkSettings") or {}).get("Networks") or {})
    registered = target["name"] in _registered_names(db)
    payload["registered"] = registered
    payload["exec_command"] = container_rules.build_exec_commands(target)
    payload["detail"] = {
        "command": raw.get("Path"),
        "args": raw.get("Args"),
        "started_at": container_rules.parse_docker_time(state.get("StartedAt")),
        "finished_at": container_rules.parse_docker_time(state.get("FinishedAt")),
        "exit_code": state.get("ExitCode"),
        "restart_count": raw.get("RestartCount"),
        "health": (state.get("Health") or {}).get("Status"),
        "networks": list(networks.keys()),
        "mount_count": len(raw.get("Mounts") or []),
        "restart_policy": ((raw.get("HostConfig") or {}).get("RestartPolicy") or {}).get("Name"),
        # 刻意不返回 Config.Env：里面可能带数据库密码 / API key
        "refusal_reason": container_rules.refusal_reason(target, registered=registered),
    }
    return ok(payload)


@router.get("/agent/containers/{container_id}/logs")
def get_container_logs(
    container_id: str,
    tail: int = Query(default=200, ge=1, le=1000),
    since: int | None = Query(default=None, description="相对现在往前多少秒"),
    timestamps: bool = Query(default=True, description="带时间戳（服务端逐行转本地时间后返回）"),
    db: Session = Depends(get_db),
):
    target = _match(_live_containers(db), container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")
    try:
        text, truncated = docker_client.container_logs(target["full_id"], tail, since)
    except docker_client.ContainerNotFound:
        raise HTTPException(status_code=404, detail="容器不存在") from None
    except docker_client.DockerUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Docker 服务不可达：{exc}") from exc

    # Docker 给的是 RFC3339 UTC，必须逐行转成 naive 北京时再出网，
    # 否则违反「全库 naive 本地时间」的约定。用户显式要求不带时间戳时原样返回。
    if timestamps:
        text = container_rules.localize_log_timestamps(text)
    return ok({
        "container_id": target["container_id"],
        "name": target["name"],
        "text": text,
        "truncated": truncated,
        "timestamps": timestamps,
        "generated_at": local_now().isoformat(),
    })


@router.get("/agent/containers/{container_id}/exec-command")
def get_container_exec_command(container_id: str, db: Session = Depends(get_db)):
    """返回宿主机上可复制执行的命令（平台刻意不提供 Web 终端 / exec 接口）。"""
    target = _match(_live_containers(db), container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")
    return ok(container_rules.build_exec_commands(target))


@router.post("/agent/containers/{container_id}/start", dependencies=[Depends(require_permission("agent:container"))])
def start_container(
    container_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(_operate(container_id, "start", None, user, db), message="started")


@router.post("/agent/containers/{container_id}/stop", dependencies=[Depends(require_permission("agent:container"))])
def stop_container(
    container_id: str,
    payload: ContainerActionIn | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reason = _require_reason(payload)
    return ok(
        _operate(container_id, "stop", payload.timeout if payload else None, user, db, reason),
        message="stopped",
    )


@router.post("/agent/containers/{container_id}/restart", dependencies=[Depends(require_permission("agent:container"))])
def restart_container(
    container_id: str,
    payload: ContainerActionIn | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reason = _require_reason(payload)
    return ok(
        _operate(container_id, "restart", payload.timeout if payload else None, user, db, reason),
        message="restarted",
    )


@router.get("/agent/container-audits")
def list_container_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    container_id: str | None = Query(default=None),
    project_key: str | None = Query(default=None),
    result: str | None = Query(default=None),
    operator: str | None = Query(default=None, description="按操作人（x-user-num）精确筛选"),
    db: Session = Depends(get_db),
):
    stmt = select(AgentContainerAudit)
    if container_id:
        stmt = stmt.where(AgentContainerAudit.container_id == container_id)
    if project_key:
        stmt = stmt.where(AgentContainerAudit.project_key == project_key)
    if result:
        stmt = stmt.where(AgentContainerAudit.result == result)
    if operator:
        stmt = stmt.where(AgentContainerAudit.operator == operator.strip())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(AgentContainerAudit.id)).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": row.id,
            "container_id": row.container_id,
            "container_name": row.container_name,
            "project_key": row.project_key,
            "action": row.action,
            "result": row.result,
            "operator": row.operator,
            "detail": row.detail,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size)
