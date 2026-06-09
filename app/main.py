from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
import logging
import sys

from app.database import engine, Base
from app import models
from app.routers import products, locations, picklists, batches, tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("warehouse-picklist-api")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="仓库拣货单 API",
    description="基于 FastAPI + SQLite 的仓库拣货管理系统，支持拣货批次、货位任务分配及完成状态回传",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"参数验证失败: {request.url} - {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "参数验证失败",
            "data": {"errors": exc.errors()},
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"数据库完整性错误: {request.url} - {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": "数据操作失败，可能存在唯一约束冲突或引用错误",
            "data": {"detail": str(exc.orig)},
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {request.url} - {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": {"detail": str(exc)},
        },
    )


@app.get("/", tags=["系统"])
async def root():
    return {
        "code": 0,
        "message": "仓库拣货单 API 服务运行中",
        "data": {
            "name": "仓库拣货单 API",
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
        },
    }


@app.get("/api/health", tags=["系统"])
async def health_check():
    return {"code": 0, "message": "success", "data": {"status": "healthy"}}


app.include_router(products.router)
app.include_router(locations.router)
app.include_router(picklists.router)
app.include_router(batches.router)
app.include_router(tasks.router)


@app.on_event("startup")
async def init_sample_data():
    from app.database import SessionLocal
    from app import crud, schemas

    db = SessionLocal()
    try:
        sample_products = [
            {"sku": "SKU001", "name": "苹果 iPhone 15", "category": "电子产品", "specification": "128GB 黑色", "unit": "台", "weight": 0.174, "barcode": "6901234567890"},
            {"sku": "SKU002", "name": "华为 Mate 60", "category": "电子产品", "specification": "256GB 白色", "unit": "台", "weight": 0.209, "barcode": "6901234567891"},
            {"sku": "SKU003", "name": "小米 14", "category": "电子产品", "specification": "512GB 蓝色", "unit": "台", "weight": 0.193, "barcode": "6901234567892"},
            {"sku": "SKU004", "name": "AirPods Pro", "category": "配件", "specification": "第二代 USB-C", "unit": "副", "weight": 0.005, "barcode": "6901234567893"},
            {"sku": "SKU005", "name": "小米充电宝", "category": "配件", "specification": "20000mAh", "unit": "个", "weight": 0.450, "barcode": "6901234567894"},
        ]
        for p in sample_products:
            if not crud.get_product_by_sku(db, p["sku"]):
                crud.create_product(db, schemas.ProductCreate(**p))
                logger.info(f"初始化示例商品: {p['sku']} - {p['name']}")

        sample_locations = [
            {"code": "A-01-01-01", "zone": "A区", "aisle": "01", "shelf": "01", "level": "01", "position": "01", "description": "A区 1号通道 1号货架 1层 1位"},
            {"code": "A-01-01-02", "zone": "A区", "aisle": "01", "shelf": "01", "level": "01", "position": "02", "description": "A区 1号通道 1号货架 1层 2位"},
            {"code": "A-01-02-01", "zone": "A区", "aisle": "01", "shelf": "02", "level": "01", "position": "01", "description": "A区 1号通道 2号货架 1层 1位"},
            {"code": "A-01-02-02", "zone": "A区", "aisle": "01", "shelf": "02", "level": "01", "position": "02", "description": "A区 1号通道 2号货架 1层 2位"},
            {"code": "B-02-01-01", "zone": "B区", "aisle": "02", "shelf": "01", "level": "01", "position": "01", "description": "B区 2号通道 1号货架 1层 1位"},
            {"code": "B-02-01-02", "zone": "B区", "aisle": "02", "shelf": "01", "level": "01", "position": "02", "description": "B区 2号通道 1号货架 1层 2位"},
        ]
        for l in sample_locations:
            if not crud.get_location_by_code(db, l["code"]):
                crud.create_location(db, schemas.LocationCreate(**l))
                logger.info(f"初始化示例货位: {l['code']}")

        sample_inventory = [
            ("SKU001", "A-01-01-01", 100),
            ("SKU001", "A-01-01-02", 50),
            ("SKU002", "A-01-02-01", 80),
            ("SKU003", "A-01-02-02", 120),
            ("SKU004", "B-02-01-01", 200),
            ("SKU005", "B-02-01-02", 150),
        ]
        for sku, code, qty in sample_inventory:
            product = crud.get_product_by_sku(db, sku)
            location = crud.get_location_by_code(db, code)
            if product and location:
                exists = db.query(models.InventoryItem).filter(
                    models.InventoryItem.product_id == product.id,
                    models.InventoryItem.location_id == location.id
                ).first()
                if not exists:
                    crud.create_inventory(
                        db,
                        schemas.InventoryItemCreate(
                            product_id=product.id,
                            location_id=location.id,
                            quantity=qty,
                            available_qty=qty,
                            reserved_qty=0,
                            lot_number=f"LOT{sku[3:]}{qty:04d}",
                        ),
                    )
                    logger.info(f"初始化示例库存: {sku}@{code} = {qty}")
    finally:
        db.close()
