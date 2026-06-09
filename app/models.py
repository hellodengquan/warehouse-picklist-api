from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"


class LocationStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    LOCKED = "locked"


class BatchStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PICKING = "picking"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PicklistStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PICKING = "picking"
    COMPLETED = "completed"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(128))
    specification = Column(String(255))
    unit = Column(String(32), default="件")
    weight = Column(Float, default=0)
    volume = Column(Float, default=0)
    status = Column(Enum(ProductStatus), default=ProductStatus.ACTIVE)
    barcode = Column(String(64))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    inventory_items = relationship("InventoryItem", back_populates="product")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    zone = Column(String(64), nullable=False)
    aisle = Column(String(32))
    shelf = Column(String(32))
    level = Column(String(32))
    position = Column(String(32))
    capacity = Column(Float, default=1)
    status = Column(Enum(LocationStatus), default=LocationStatus.AVAILABLE)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    inventory_items = relationship("InventoryItem", back_populates="location")
    pick_tasks = relationship("PickTask", back_populates="location")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    available_qty = Column(Integer, nullable=False, default=0)
    reserved_qty = Column(Integer, nullable=False, default=0)
    lot_number = Column(String(64))
    expiry_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("Product", back_populates="inventory_items")
    location = relationship("Location", back_populates="inventory_items")


class PickBatch(Base):
    __tablename__ = "pick_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_no = Column(String(64), unique=True, index=True, nullable=False)
    batch_type = Column(String(32), default="normal")
    priority = Column(Integer, default=5)
    status = Column(Enum(BatchStatus), default=BatchStatus.PENDING)
    picker = Column(String(64))
    total_orders = Column(Integer, default=0)
    total_skus = Column(Integer, default=0)
    total_qty = Column(Integer, default=0)
    completed_qty = Column(Integer, default=0)
    exception_count = Column(Integer, default=0)
    planned_start_at = Column(DateTime(timezone=True))
    actual_start_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    remark = Column(Text)
    created_by = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    picklists = relationship("Picklist", back_populates="batch")


class Picklist(Base):
    __tablename__ = "picklists"

    id = Column(Integer, primary_key=True, index=True)
    picklist_no = Column(String(64), unique=True, index=True, nullable=False)
    batch_id = Column(Integer, ForeignKey("pick_batches.id"))
    order_no = Column(String(64))
    customer = Column(String(255))
    priority = Column(Integer, default=5)
    status = Column(Enum(PicklistStatus), default=PicklistStatus.PENDING)
    total_lines = Column(Integer, default=0)
    total_qty = Column(Integer, default=0)
    picked_qty = Column(Integer, default=0)
    short_qty = Column(Integer, default=0)
    picker = Column(String(64))
    wave_no = Column(String(64))
    delivery_address = Column(Text)
    planned_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    remark = Column(Text)
    created_by = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    batch = relationship("PickBatch", back_populates="picklists")
    tasks = relationship("PickTask", back_populates="picklist")


class PickTask(Base):
    __tablename__ = "pick_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_no = Column(String(64), unique=True, index=True, nullable=False)
    picklist_id = Column(Integer, ForeignKey("picklists.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_sku = Column(String(64), nullable=False)
    product_name = Column(String(255), nullable=False)
    location_code = Column(String(64), nullable=False)
    lot_number = Column(String(64))
    planned_qty = Column(Integer, nullable=False)
    picked_qty = Column(Integer, default=0)
    short_qty = Column(Integer, default=0)
    damage_qty = Column(Integer, default=0)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    picker = Column(String(64))
    sort_order = Column(Integer, default=0)
    assigned_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    exception_code = Column(String(32))
    exception_note = Column(Text)
    scan_code = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    picklist = relationship("Picklist", back_populates="tasks")
    location = relationship("Location", back_populates="pick_tasks")
