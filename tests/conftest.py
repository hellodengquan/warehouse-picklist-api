import pytest
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app as original_app
from app import crud, schemas


@pytest.fixture(scope="function")
def db_engine():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_url = f"sqlite:///{tmp.name}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture(scope="function")
def db_session(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def app(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    original_app.dependency_overrides[get_db] = override_get_db
    yield original_app
    original_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def seed_data(db_session):
    products = [
        schemas.ProductCreate(sku="SKU001", name="测试商品A", category="电子产品", specification="spec1", unit="台", weight=0.5, barcode="1111111111111"),
        schemas.ProductCreate(sku="SKU002", name="测试商品B", category="电子产品", specification="spec2", unit="台", weight=0.3, barcode="2222222222222"),
        schemas.ProductCreate(sku="SKU003", name="测试商品C", category="配件", specification="spec3", unit="个", weight=0.1, barcode="3333333333333"),
    ]
    created_products = [crud.create_product(db_session, p) for p in products]

    locations = [
        schemas.LocationCreate(code="A-01-01-01", zone="A区", aisle="01", shelf="01", level="01", position="01"),
        schemas.LocationCreate(code="A-01-01-02", zone="A区", aisle="01", shelf="01", level="01", position="02"),
        schemas.LocationCreate(code="B-02-03-04", zone="B区", aisle="02", shelf="03", level="03", position="04"),
    ]
    created_locations = [crud.create_location(db_session, l) for l in locations]

    inventories = [
        schemas.InventoryItemCreate(product_id=created_products[0].id, location_id=created_locations[0].id, quantity=100, available_qty=100, reserved_qty=0, lot_number="LOT001"),
        schemas.InventoryItemCreate(product_id=created_products[0].id, location_id=created_locations[1].id, quantity=50, available_qty=50, reserved_qty=0, lot_number="LOT002"),
        schemas.InventoryItemCreate(product_id=created_products[1].id, location_id=created_locations[0].id, quantity=80, available_qty=80, reserved_qty=0, lot_number="LOT003"),
        schemas.InventoryItemCreate(product_id=created_products[2].id, location_id=created_locations[2].id, quantity=200, available_qty=200, reserved_qty=0, lot_number="LOT004"),
    ]
    created_inventories = [crud.create_inventory(db_session, inv) for inv in inventories]

    db_session.commit()

    return {
        "products": created_products,
        "locations": created_locations,
        "inventories": created_inventories,
    }
