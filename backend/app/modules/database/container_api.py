"""容器实况接口：容器列表 / 详情 / 日志 / exec 命令 / 启停重启 / 操作审计。

**读写守卫分离**：本文件里的读接口由父 router（`api.py`）的
`require_roles("admin", "viewer", "database_admin")` 覆盖；三个写接口**逐路由**再加
`require_roles("admin", "database_container_admin")`。

`database_container_admin` 刻意**不复用** `database_admin`：台账编辑权与「重启宿主机
数据库容器」的影响面差一个量级，复用等于静默提权。未在 IdP 侧配置该角色前，实际
只有 `admin` 可用（OIDC 关闭时仍是匿名 admin）。

注意：本 router **不带 prefix**，它被 `api.py` 的父 router（`prefix="/api/v1"`）include，
因此这里的 "/database-containers" 实际暴露为 "/api/v1/database-containers"。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import get_db
from app.core.response import ok, paginated
from app.core.timeutil import local_now
from app.modules.database import containers as container_rules
from app.modules.database import docker_client
from app.modules.database.models import DatabaseContainerAudit
from app.modules.database.schemas import ContainerActionIn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["database-container"])

# 控制面动作的角色：viewer 能看，但不能启停
_ACTION_ROLES = ("admin", "database_container_admin")


def _live_containers() -> list[dict]:
    """实况容器列表；Docker 不可达时抛 503（读列表的接口另行降级为 200）。"""
    try:
        return [container_rules.serialize_container(c) for c in docker_client.list_containers()]
    except docker_client.DockerUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Docker 服务不可达：{exc}") from exc


def _match(containers: list[dict], container_id: str) -> dict | None:
    """按 full ID / 12 位短 ID / 容器名定位。"""
    token = (container_id or "").strip()
    for item in containers:
        if token and token in (item["full_id"], item["container_id"], item["name"]):
            return item
    return None


def _record(db: Session, target: dict, action: str, result: str, user: CurrentUser, detail: dict) -> None:
    """写审计。

    **审计写失败绝不能把成功的操作变成 500**，所以这里单独兜住异常。
    """
    try:
        db.add(
            DatabaseContainerAudit(
                container_id=target["container_id"],
                container_name=target["name"],
                managed_type=target["managed_type"],
                action=action,
                result=result,
                operator=user.username,
                detail=detail,
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("写入容器操作审计失败 container=%s action=%s", target.get("container_id"), action)


def _operate(container_id: str, action: str, timeout: int | None, user: CurrentUser, db: Session) -> dict:
    live = _live_containers()
    target = _match(live, container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")

    reason = container_rules.refusal_reason(target)
    if reason:
        # 受保护 / 未识别 → **在调用 Docker 之前**就拒绝，并留痕
        _record(db, target, action, "refused", user, {"reason": reason})
        raise HTTPException(status_code=409, detail=reason)

    try:
        if action == "start":
            docker_client.start_container(target["full_id"])
        elif action == "stop":
            docker_client.stop_container(target["full_id"], timeout)
        else:
            docker_client.restart_container(target["full_id"], timeout)
    except docker_client.ContainerNotFound as exc:
        _record(db, target, action, "failed", user, {"error": str(exc)})
        raise HTTPException(status_code=404, detail="容器不存在") from exc
    except docker_client.DockerUnavailable as exc:
        _record(db, target, action, "failed", user, {"error": str(exc)})
        raise HTTPException(status_code=503, detail=f"操作失败：{exc}") from exc

    _record(db, target, action, "success", user, {"timeout": timeout})
    return {
        "container_id": target["container_id"],
        "name": target["name"],
        "action": action,
        "result": "success",
    }


@router.get("/database-containers")
def list_containers(
    managed_type: str | None = Query(default=None),
    state: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_protected: bool = Query(default=True),
):
    """扁平容器列表。Docker 不可达时**仍返回 200 + degraded**，由页面显示告警条。"""
    try:
        live = [container_rules.serialize_container(c) for c in docker_client.list_containers()]
    except docker_client.DockerUnavailable as exc:
        return ok({
            "items": [],
            "total": 0,
            "degraded": True,
            "error": str(exc),
            "generated_at": local_now().isoformat(),
        })

    items = live
    if managed_type:
        items = [c for c in items if c["managed_type"] == managed_type]
    if state:
        items = [c for c in items if c["state"] == state]
    if q:
        keyword = q.strip().lower()
        items = [c for c in items if keyword in c["name"].lower() or keyword in c["image"].lower()]
    if not include_protected:
        items = [c for c in items if not c["protected"]]
    return ok({
        "items": items,
        "total": len(items),
        "degraded": False,
        "error": None,
        "generated_at": local_now().isoformat(),
    })


@router.get("/database-containers/{container_id}")
def get_container(container_id: str):
    target = _match(_live_containers(), container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")

    payload: dict = {"container": target, "detail": None}
    try:
        raw = docker_client.inspect_container(target["full_id"])
    except docker_client.DockerUnavailable:
        return ok(payload)  # 详情属增强信息，拿不到就只回摘要
    except docker_client.ContainerNotFound:
        raise HTTPException(status_code=404, detail="容器不存在") from None

    state = raw.get("State") or {}
    networks = ((raw.get("NetworkSettings") or {}).get("Networks") or {})
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
        # 刻意不返回 Config.Env：里面可能带数据库密码 / API key
    }
    return ok(payload)


@router.get("/database-containers/{container_id}/logs")
def get_container_logs(container_id: str, tail: int = Query(default=200, ge=1, le=1000)):
    target = _match(_live_containers(), container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")
    try:
        text, truncated = docker_client.container_logs(target["full_id"], tail)
    except docker_client.ContainerNotFound:
        raise HTTPException(status_code=404, detail="容器不存在") from None
    except docker_client.DockerUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Docker 服务不可达：{exc}") from exc
    return ok({
        "container_id": target["container_id"],
        "name": target["name"],
        "text": text,
        "truncated": truncated,
        "generated_at": local_now().isoformat(),
    })


@router.get("/database-containers/{container_id}/exec-command")
def get_container_exec_command(container_id: str):
    """返回宿主机上可复制执行的命令（v1 刻意不提供 Web 终端）。"""
    target = _match(_live_containers(), container_id)
    if target is None:
        raise HTTPException(status_code=404, detail="容器不存在")
    return ok(container_rules.build_exec_commands(target))


@router.post("/database-containers/{container_id}/start", dependencies=[Depends(require_roles(*_ACTION_ROLES))])
def start_container(
    container_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(_operate(container_id, "start", None, user, db), message="started")


@router.post("/database-containers/{container_id}/stop", dependencies=[Depends(require_roles(*_ACTION_ROLES))])
def stop_container(
    container_id: str,
    payload: ContainerActionIn | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(_operate(container_id, "stop", payload.timeout if payload else None, user, db), message="stopped")


@router.post("/database-containers/{container_id}/restart", dependencies=[Depends(require_roles(*_ACTION_ROLES))])
def restart_container(
    container_id: str,
    payload: ContainerActionIn | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(_operate(container_id, "restart", payload.timeout if payload else None, user, db), message="restarted")


@router.get("/database-container-audits")
def list_container_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    container_id: str | None = Query(default=None),
    result: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(DatabaseContainerAudit)
    if container_id:
        stmt = stmt.where(DatabaseContainerAudit.container_id == container_id)
    if result:
        stmt = stmt.where(DatabaseContainerAudit.result == result)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(DatabaseContainerAudit.id)).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": row.id,
            "container_id": row.container_id,
            "container_name": row.container_name,
            "managed_type": row.managed_type,
            "action": row.action,
            "result": row.result,
            "operator": row.operator,
            "detail": row.detail,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size)
