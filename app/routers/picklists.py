from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import schemas, crud, models

router = APIRouter(prefix="/api/picklists", tags=["拣货单管理"])


@router.post("", response_model=schemas.Picklist, summary="创建拣货单")
def create_picklist(picklist_in: schemas.PicklistCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_picklist(db, picklist_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", summary="拣货单列表")
def list_picklists(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[schemas.PicklistStatus] = Query(None),
    batch_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None, description="搜索拣货单号/订单号"),
    picker: Optional[str] = Query(None, description="拣货员"),
    db: Session = Depends(get_db),
):
    items, total = crud.list_picklists(db, page, page_size, status, batch_id, keyword, picker)
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": [schemas.Picklist.model_validate(item).model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{picklist_id}", response_model=schemas.Picklist, summary="拣货单详情")
def get_picklist(picklist_id: int, db: Session = Depends(get_db)):
    picklist = crud.get_picklist(db, picklist_id)
    if not picklist:
        raise HTTPException(status_code=404, detail="拣货单不存在")
    return picklist


@router.put("/{picklist_id}", response_model=schemas.Picklist, summary="更新拣货单")
def update_picklist(
    picklist_id: int,
    picklist_in: schemas.PicklistUpdate,
    db: Session = Depends(get_db),
):
    picklist = crud.get_picklist(db, picklist_id)
    if not picklist:
        raise HTTPException(status_code=404, detail="拣货单不存在")
    update_data = picklist_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(picklist, field, value)
    db.commit()
    db.refresh(picklist)
    return picklist
