"""项目分组与分类规则接口。

读接口由父 router 覆盖；写接口逐路由加 `require_roles("admin", "agent_admin")`
（台账编辑是可逆的库内操作，与容器启停刻意分开授权）。

本 router 不带 prefix，被 `api.py` 的父 router include（同 container_api.py）。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.core.response import created, ok
from app.modules.agent import containers as container_rules
from app.modules.agent import docker_client
from app.modules.agent.models import AgentProjectRule
from app.modules.agent.schemas import ProjectRuleIn, ProjectRuleUpdate, RuleEnabledIn

router = APIRouter(tags=["agent-platform"])

_LEDGER_ROLES = ("admin", "agent_admin")


def _serialize(rule: AgentProjectRule) -> dict:
    return {
        "id": rule.id,
        "project_key": rule.project_key,
        "project_name": rule.project_name,
        "enabled": rule.enabled,
        "compose_project_names": rule.compose_project_names or [],
        "container_name_patterns": rule.container_name_patterns or [],
        "description": rule.description,
        "priority": rule.priority,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _get(db: Session, project_key: str) -> AgentProjectRule:
    rule = db.scalar(select(AgentProjectRule).where(AgentProjectRule.project_key == project_key))
    if rule is None:
        raise HTTPException(status_code=404, detail="分类规则不存在")
    return rule


@router.get("/agent/projects")
def list_projects(db: Session = Depends(get_db)):
    """项目汇总：每个项目的容器总数 / 运行中 / 已停止，另带未分类与冲突两个桶。

    Docker 不可达时容器数归零、`degraded=true` —— 规则本身照常返回。
    """
    rules = container_rules.load_rules(db)
    try:
        live = container_rules.list_serialized_containers(db)
    except docker_client.DockerUnavailable as exc:
        summary = container_rules.project_summary(rules, [])
        return ok({
            **summary,
            "degraded": True,
            "error": str(exc),
            "conflicts": container_rules.detect_rule_conflicts(rules),
        })

    return ok({
        **container_rules.project_summary(rules, live),
        "degraded": False,
        "error": None,
        "conflicts": container_rules.detect_rule_conflicts(rules),
    })


@router.get("/agent/project-rules")
def list_project_rules(
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AgentProjectRule).order_by(AgentProjectRule.priority, AgentProjectRule.project_key)
    if enabled is not None:
        stmt = stmt.where(AgentProjectRule.enabled.is_(enabled))
    rules = list(db.scalars(stmt).all())
    return ok({
        "items": [_serialize(r) for r in rules],
        "total": len(rules),
        # 规则之间的**显式**重复声明（同一个 compose 项目名 / 同一段正则出现在多条规则里）
        "conflicts": container_rules.detect_rule_conflicts(rules),
    })


@router.post("/agent/project-rules", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles(*_LEDGER_ROLES))])
def create_project_rule(payload: ProjectRuleIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(AgentProjectRule).where(AgentProjectRule.project_key == payload.project_key))
    if exists is not None:
        raise HTTPException(status_code=409, detail="项目 key 已存在")
    rule = AgentProjectRule(
        project_key=payload.project_key,
        project_name=payload.project_name,
        enabled=payload.enabled,
        compose_project_names=payload.compose_project_names,
        container_name_patterns=payload.container_name_patterns,
        description=payload.description,
        priority=payload.priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return created(_serialize(rule))


@router.get("/agent/project-rules/{project_key}")
def get_project_rule(project_key: str, db: Session = Depends(get_db)):
    return ok(_serialize(_get(db, project_key)))


@router.put("/agent/project-rules/{project_key}", dependencies=[Depends(require_roles(*_LEDGER_ROLES))])
def update_project_rule(project_key: str, payload: ProjectRuleUpdate, db: Session = Depends(get_db)):
    rule = _get(db, project_key)
    for field in ("project_name", "enabled", "compose_project_names",
                  "container_name_patterns", "description", "priority"):
        value = getattr(payload, field)
        if value is not None:
            setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return ok(_serialize(rule))


@router.patch("/agent/project-rules/{project_key}/enabled", dependencies=[Depends(require_roles(*_LEDGER_ROLES))])
def set_project_rule_enabled(project_key: str, payload: RuleEnabledIn, db: Session = Depends(get_db)):
    rule = _get(db, project_key)
    rule.enabled = payload.enabled
    db.commit()
    db.refresh(rule)
    return ok(_serialize(rule))


@router.delete("/agent/project-rules/{project_key}", dependencies=[Depends(require_roles(*_LEDGER_ROLES))])
def delete_project_rule(project_key: str, db: Session = Depends(get_db)):
    """删除的**只是分类规则**，不会碰任何实际 Docker 容器。

    删掉规则后，原本归到该项目的容器会退回「未分类」并变为只读 —— 这是预期的：
    归属不明就不该有启停权。
    """
    rule = _get(db, project_key)
    db.delete(rule)
    db.commit()
    return ok({"project_key": project_key}, message="deleted")
