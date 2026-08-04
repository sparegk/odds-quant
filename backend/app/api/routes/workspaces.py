from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.workspaces import WorkspaceView, WorkspaceWrite
from app.services.workspaces import delete_workspace, list_workspaces, save_workspace

router = APIRouter(
    prefix="/workspaces",
    tags=["research-workspaces"],
    dependencies=[Depends(require_admin_key)],
)
Database = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[WorkspaceView])
def index(
    database: Database,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[WorkspaceView]:
    return list_workspaces(database, limit=limit, offset=offset)


@router.put("", response_model=WorkspaceView)
def upsert(request: WorkspaceWrite, database: Database) -> WorkspaceView:
    return save_workspace(database, request)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(workspace_id: int, database: Database) -> Response:
    if not delete_workspace(database, workspace_id):
        raise HTTPException(status_code=404, detail="Research workspace not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
