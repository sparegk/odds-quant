from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ResearchWorkspace
from app.schemas.workspaces import WorkspaceView, WorkspaceWrite


def list_workspaces(database: Session, *, limit: int = 50, offset: int = 0) -> list[WorkspaceView]:
    records = database.scalars(
        select(ResearchWorkspace)
        .order_by(ResearchWorkspace.updated_at.desc(), ResearchWorkspace.name)
        .offset(offset)
        .limit(limit)
    ).all()
    return [_view(record) for record in records]


def save_workspace(database: Session, request: WorkspaceWrite) -> WorkspaceView:
    normalized_name = request.name.strip()
    record = database.scalar(
        select(ResearchWorkspace).where(ResearchWorkspace.name == normalized_name)
    )
    now = datetime.now(UTC)
    items = [item.model_dump(mode="json") for item in request.items]
    if record is None:
        record = ResearchWorkspace(name=normalized_name, items=items, updated_at=now)
        database.add(record)
    else:
        record.items = items
        record.updated_at = now
    database.commit()
    database.refresh(record)
    return _view(record)


def delete_workspace(database: Session, workspace_id: int) -> bool:
    record = database.get(ResearchWorkspace, workspace_id)
    if record is None:
        return False
    database.delete(record)
    database.commit()
    return True


def _view(record: ResearchWorkspace) -> WorkspaceView:
    return WorkspaceView.model_validate(
        {
            "id": record.id,
            "name": record.name,
            "items": record.items,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )
