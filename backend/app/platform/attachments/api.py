import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.platform.attachments.models import Attachment

router = APIRouter(prefix="/api/v1", tags=["attachments"])

ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "document": {".txt", ".md", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".rtf", ".log", ".json", ".xml", ".conf", ".yaml", ".yml", ".ini", ".cfg", ".toml"},
    "spreadsheet": {".xls", ".xlsx", ".csv"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"},
    "video": {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"},
}


def _classify_file(filename: str) -> str | None:
    ext = os.path.splitext(filename)[1].lower()
    for category, exts in ALLOWED_EXTENSIONS.items():
        if ext in exts:
            return category
    return None


def _serialize_attachment(a: Attachment) -> dict:
    return {
        "id": a.id,
        "filename": a.filename,
        "stored_name": a.stored_name,
        "uploader": a.uploader,
        "category": a.category,
        "content_type": a.content_type,
        "size": a.size,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.post("/files", status_code=status.HTTP_201_CREATED)
def upload_file(
    file: UploadFile = File(...),
    uploader: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """上传附件：保存到专属目录，库内记录文件地址与上传人。"""
    filename = file.filename or "unnamed"
    category = _classify_file(filename)
    if category is None:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{os.path.splitext(filename)[1] or '未知'}")

    ext = os.path.splitext(filename)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / stored_name
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("file too large")
                out.write(chunk)
    except ValueError:
        if dest.exists():
            dest.unlink()
        raise HTTPException(status_code=413, detail=f"文件超过 {settings.max_upload_size_mb}MB 限制")
    finally:
        file.file.close()

    att = Attachment(
        filename=filename,
        stored_name=stored_name,
        uploader=(uploader or "").strip() or None,
        category=category,
        content_type=file.content_type or "application/octet-stream",
        size=size,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"code": 0, "message": "success", "data": _serialize_attachment(att)}


@router.get("/files")
def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """附件目录：分页列表 + 按类别筛选。"""
    stmt = select(Attachment)
    if category:
        stmt = stmt.where(Attachment.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(Attachment.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [_serialize_attachment(a) for a in rows]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


def _file_response(a: Attachment, inline: bool) -> FileResponse:
    path = Path(settings.upload_dir) / a.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path,
        filename=a.filename,
        media_type=a.content_type or "application/octet-stream",
        content_disposition_type="inline" if inline else "attachment",
    )


@router.get("/files/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db)):
    """下载附件（Content-Disposition: attachment）。"""
    a = db.get(Attachment, file_id)
    if a is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    return _file_response(a, inline=False)


@router.get("/files/{file_id}/preview")
def preview_file(file_id: int, db: Session = Depends(get_db)):
    """预览附件（inline，图片/PDF 可在浏览器直接查看）。"""
    a = db.get(Attachment, file_id)
    if a is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    return _file_response(a, inline=True)


@router.delete("/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    """删除附件（删除磁盘文件 + 库内记录）。"""
    a = db.get(Attachment, file_id)
    if a is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    path = Path(settings.upload_dir) / a.stored_name
    if path.exists():
        path.unlink()
    db.delete(a)
    db.commit()
    return {"code": 0, "message": "deleted", "data": {"id": file_id}}
