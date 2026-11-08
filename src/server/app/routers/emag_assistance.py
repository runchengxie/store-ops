"""Administrator-only deterministic local eMAG assistance."""
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from app.core.security import require_admin
from app.services import emag_decision_support, emag_preflight, emag_promotion

router=APIRouter(dependencies=[Depends(require_admin)])


class Promotion(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    snapshot_id:str=Field(min_length=1,max_length=100)
    discount_pct:str='0'
    voucher_pct:str='0'
    stacking:Literal['unknown','sequential']='unknown'
    commission_reduction_pct:str='0'
    support_ex_vat_ron:str|None=None
    extra_cost_ron:str|None=None


def call(fn,*args):
    try:return fn(*args)
    except OSError as exc:raise HTTPException(404,str(exc)) from exc
    except OverflowError as exc:raise HTTPException(413,str(exc)) from exc
    except ValueError as exc:raise HTTPException(409 if 'stale' in str(exc) else 422,str(exc)) from exc


@router.get('/stores/{store_id}/decision-support')
def decision_support(store_id:str):
    return call(emag_decision_support.view,store_id)


@router.post('/stores/{store_id}/promotion-check/{product_id}')
def promotion_check(store_id:str,product_id:str,body:Promotion):
    return call(emag_promotion.check,store_id,body.snapshot_id,product_id,body.model_dump(exclude={'snapshot_id'}))


@router.post('/stores/{store_id}/preflight')
async def preflight(store_id:str,snapshot_id:str=Form(...,min_length=1,max_length=100),file:UploadFile=File(...)):
    try:content=await file.read(emag_preflight.MAX_BYTES+1)
    finally:await file.close()
    return call(emag_preflight.check,store_id,snapshot_id,file.filename,content)
