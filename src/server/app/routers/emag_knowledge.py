"""Administrator-only local evidence reads; imports are owner CLI only."""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import require_admin
from app.services import emag_knowledge as service

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get('/knowledge/status')
def status():
    return service.status()


@router.get('/knowledge/search')
def search(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=5, ge=1, le=20)):
    try:
        return service.search(q, limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/knowledge/sources/{source_id}')
def source(source_id: str, revision: str | None = Query(default=None, min_length=1, max_length=64)):
    try:
        return service.source(source_id, revision)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
