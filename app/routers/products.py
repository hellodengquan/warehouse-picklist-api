from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import schemas, crud, models

router = APIRouter(prefix="/api/products", tags=["商品管理"])


@router.post("", response_model=schemas.Product, summary="创建商品")
def create_product(product_in: schemas.ProductCreate, db: Session = Depends(get_db)):
    existing = crud.get_product_by_sku(db, product_in.sku)
    if existing:
        raise HTTPException(status_code=400, detail=f"SKU {product_in.sku} 已存在")
    return crud.create_product(db, product_in)


@router.get("", summary="商品列表")
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    status: Optional[schemas.ProductStatus] = Query(None),
    db: Session = Depends(get_db),
):
    items, total = crud.list_products(db, page, page_size, keyword, status)
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": [schemas.Product.model_validate(item).model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{product_id}", response_model=schemas.Product, summary="商品详情")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product


@router.put("/{product_id}", response_model=schemas.Product, summary="更新商品")
def update_product(
    product_id: int,
    product_in: schemas.ProductUpdate,
    db: Session = Depends(get_db),
):
    product = crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return crud.update_product(db, product, product_in)


@router.post("/inventory", response_model=schemas.InventoryItem, summary="创建库存记录")
def create_inventory(inv_in: schemas.InventoryItemCreate, db: Session = Depends(get_db)):
    product = crud.get_product(db, inv_in.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    location = crud.get_location(db, inv_in.location_id)
    if not location:
        raise HTTPException(status_code=404, detail="货位不存在")
    return crud.create_inventory(db, inv_in)
