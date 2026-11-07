"""Authenticated platform-neutral overview; explicit extensions keep their own routes."""
from dataclasses import asdict
from fastapi import APIRouter,Depends,HTTPException
from app.core.security import require_admin
from app.platforms import registry

router=APIRouter(dependencies=[Depends(require_admin)])


@router.get('/platforms')
def platforms():
    return [asdict(d) for d in registry.descriptors()]


@router.get('/stores')
def stores():
    return registry.stores()


@router.get('/stores/{store_id}/overview')
def overview(store_id: str):
    try:
        return registry.overview(store_id)
    except FileNotFoundError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (OSError,ValueError) as exc:
        raise HTTPException(409,str(exc)) from exc
