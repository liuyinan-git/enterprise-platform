from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.config import settings
from app.core.db import get_db
from app.core.security import mask_secret
from app.platform.notifications.schemas import WecomConfigIn, WecomTestIn
from app.platform.notifications.service import get_or_create_config
from app.platform.notifications.wecom import send_markdown

router = APIRouter(
    prefix="/api/v1",
    tags=["notifications"],
    dependencies=[Depends(require_roles("admin"))],
)


def _wecom_config_dict(cfg) -> dict:
    return {
        "corpid": cfg.corpid,
        "corpsecret_masked": mask_secret(cfg.corpsecret),
        "agentid": cfg.agentid,
        "touser": cfg.touser,
        "enabled": cfg.enabled,
        "notify_min_severity": cfg.notify_min_severity,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("/wecom/config")
def get_wecom_config(db: Session = Depends(get_db)):
    """管理端：读取企业微信配置（密钥脱敏）。"""
    cfg = get_or_create_config(db)
    db.commit()
    return {"code": 0, "message": "success", "data": _wecom_config_dict(cfg)}


@router.put("/wecom/config")
def update_wecom_config(payload: WecomConfigIn, db: Session = Depends(get_db)):
    """管理端：保存企业微信配置（corpsecret 留空或 **** 开头则不修改）。"""
    cfg = get_or_create_config(db)
    cfg.corpid = payload.corpid
    if payload.corpsecret and not payload.corpsecret.startswith("****"):
        cfg.corpsecret = payload.corpsecret
    cfg.agentid = payload.agentid
    cfg.touser = payload.touser
    cfg.enabled = payload.enabled
    cfg.notify_min_severity = payload.notify_min_severity
    db.commit()
    db.refresh(cfg)
    return {"code": 0, "message": "success", "data": _wecom_config_dict(cfg)}


@router.post("/wecom/test")
def test_wecom(payload: WecomTestIn, db: Session = Depends(get_db)):
    """管理端：发送测试消息（touser 留空则用已配置的默认接收人）。"""
    cfg = get_or_create_config(db)
    db.commit()
    if not cfg.corpid or not cfg.corpsecret or not cfg.agentid:
        raise HTTPException(status_code=400, detail="企业微信未配置完整（corpid/corpsecret/agentid）")
    touser = payload.touser or cfg.touser
    if not touser:
        raise HTTPException(status_code=400, detail="未配置接收人 touser")
    content = payload.content or "这是一条测试消息"
    try:
        result = send_markdown(cfg.corpid, cfg.corpsecret, cfg.agentid, touser, content, settings.wecom_timeout_seconds)
        return {"code": 0, "message": "success", "data": {"errcode": result.get("errcode"), "errmsg": result.get("errmsg")}}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"发送失败：{exc}") from exc
