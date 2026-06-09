from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app import schemas, crud, models

router = APIRouter(prefix="/api/batches", tags=["拣货批次管理"])


@router.post("", response_model=schemas.PickBatch, summary="创建拣货批次")
def create_pick_batch(batch_in: schemas.PickBatchCreate, db: Session = Depends(get_db)):
    return crud.create_pick_batch(db, batch_in)


@router.get("", summary="拣货批次列表")
def list_pick_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[schemas.BatchStatus] = Query(None),
    picker: Optional[str] = Query(None, description="拣货员"),
    keyword: Optional[str] = Query(None, description="搜索批次号"),
    db: Session = Depends(get_db),
):
    items, total = crud.list_pick_batches(db, page, page_size, status, picker, keyword)
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": [schemas.PickBatch.model_validate(item).model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{batch_id}", response_model=schemas.PickBatch, summary="拣货批次详情")
def get_pick_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = crud.get_pick_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="拣货批次不存在")
    return batch


@router.put("/{batch_id}", response_model=schemas.PickBatch, summary="更新拣货批次")
def update_pick_batch(
    batch_id: int,
    batch_in: schemas.PickBatchUpdate,
    db: Session = Depends(get_db),
):
    batch = crud.get_pick_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="拣货批次不存在")
    update_data = batch_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(batch, field, value)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/{batch_id}/picklists", response_model=schemas.PickBatch, summary="向批次添加拣货单")
def add_picklists_to_batch(
    batch_id: int,
    data: schemas.PickBatchAddPicklists,
    db: Session = Depends(get_db),
):
    batch = crud.add_picklists_to_batch(db, batch_id, data.picklist_ids)
    if not batch:
        raise HTTPException(status_code=404, detail="拣货批次不存在")
    return batch


@router.post("/{batch_id}/assign", response_model=schemas.PickBatch, summary="分配拣货员（任务分配）")
def assign_batch(
    batch_id: int,
    data: schemas.PickBatchAssign,
    db: Session = Depends(get_db),
):
    batch = crud.assign_batch(db, batch_id, data)
    if not batch:
        raise HTTPException(status_code=404, detail="拣货批次不存在")
    return batch


@router.post("/{batch_id}/start", response_model=schemas.PickBatch, summary="开始拣货批次")
def start_batch(
    batch_id: int,
    data: Optional[schemas.PickTaskStart] = None,
    db: Session = Depends(get_db),
):
    batch = crud.get_pick_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="拣货批次不存在")
    if batch.status == models.BatchStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="批次已完成，无法开始")
    if batch.status == models.BatchStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="批次已取消")
    picker = data.picker if data else None
    return crud.start_batch(db, batch_id, picker)
