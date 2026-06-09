from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import schemas, crud

router = APIRouter(prefix="/api/locations", tags=["货位管理"])


@router.post("", response_model=schemas.Location, summary="创建货位")
def create_location(location_in: schemas.LocationCreate, db: Session = Depends(get_db)):
    existing = crud.get_location_by_code(db, location_in.code)
    if existing:
        raise HTTPException(status_code=400, detail=f"货位编码 {location_in.code} 已存在")
    return crud.create_location(db, location_in)


@router.get("", summary="货位列表")
def list_locations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    zone: Optional[str] = Query(None, description="库区"),
    status: Optional[schemas.LocationStatus] = Query(None),
    db: Session = Depends(get_db),
):
    items, total = crud.list_locations(db, page, page_size, keyword, zone, status)
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": [schemas.Location.model_validate(item).model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{location_id}", response_model=schemas.Location, summary="货位详情")
def get_location(location_id: int, db: Session = Depends(get_db)):
    location = crud.get_location(db, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="货位不存在")
    return location


@router.put("/{location_id}", response_model=schemas.Location, summary="更新货位")
def update_location(
    location_id: int,
    location_in: schemas.LocationUpdate,
    db: Session = Depends(get_db),
):
    location = crud.get_location(db, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="货位不存在")
    return crud.update_location(db, location, location_in)
