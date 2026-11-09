"""Authenticated platform-neutral overview; explicit extensions keep their own routes."""
from dataclasses import asdict
from fastapi import APIRouter,BackgroundTasks,Depends,HTTPException
from pydantic import BaseModel, ConfigDict, Field
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


class MonitoringControl(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paused: bool = Field(strict=True)
    revision: int = Field(ge=0, strict=True)


@router.post('/stores/{store_id}/control')
def monitoring_control(store_id: str, body: MonitoringControl, actor=Depends(require_admin)):
    from app.services import automation_control
    try:
        registry.overview(store_id)
        return automation_control.set_paused(store_id, body.paused, body.revision, str(actor))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


class BrowserCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int | None = Field(default=None, ge=0, strict=True)


@router.post('/stores/{store_id}/browser-check')
def browser_check(store_id: str, body: BrowserCheck, background: BackgroundTasks, actor=Depends(require_admin)):
    from app.services import browser_tasks
    try:
        registry.overview(store_id)
        task = browser_tasks.request(store_id, body.revision, str(actor))
        if task['state'] == 'queued':
            background.add_task(browser_tasks.launch, store_id, task['task_id'])
        return task
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
