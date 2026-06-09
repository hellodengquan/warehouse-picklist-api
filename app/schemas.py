from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"


class LocationStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    LOCKED = "locked"


class BatchStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PICKING = "picking"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PicklistStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PICKING = "picking"
    COMPLETED = "completed"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"


class ProductBase(BaseModel):
    sku: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    category: Optional[str] = Field(None, max_length=128)
    specification: Optional[str] = Field(None, max_length=255)
    unit: Optional[str] = Field("件", max_length=32)
    weight: Optional[float] = Field(0, ge=0)
    volume: Optional[float] = Field(0, ge=0)
    status: ProductStatus = ProductStatus.ACTIVE
    barcode: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    specification: Optional[str] = None
    unit: Optional[str] = None
    weight: Optional[float] = None
    volume: Optional[float] = None
    status: Optional[ProductStatus] = None
    barcode: Optional[str] = None
    description: Optional[str] = None


class Product(ProductBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LocationBase(BaseModel):
    code: str = Field(..., max_length=64)
    zone: str = Field(..., max_length=64)
    aisle: Optional[str] = Field(None, max_length=32)
    shelf: Optional[str] = Field(None, max_length=32)
    level: Optional[str] = Field(None, max_length=32)
    position: Optional[str] = Field(None, max_length=32)
    capacity: Optional[float] = Field(1, ge=0)
    status: LocationStatus = LocationStatus.AVAILABLE
    description: Optional[str] = None


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    zone: Optional[str] = None
    aisle: Optional[str] = None
    shelf: Optional[str] = None
    level: Optional[str] = None
    position: Optional[str] = None
    capacity: Optional[float] = None
    status: Optional[LocationStatus] = None
    description: Optional[str] = None


class Location(LocationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InventoryItemBase(BaseModel):
    product_id: int
    location_id: int
    quantity: int = Field(..., ge=0)
    available_qty: Optional[int] = Field(0, ge=0)
    reserved_qty: Optional[int] = Field(0, ge=0)
    lot_number: Optional[str] = Field(None, max_length=64)
    expiry_date: Optional[datetime] = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    quantity: Optional[int] = None
    available_qty: Optional[int] = None
    reserved_qty: Optional[int] = None
    lot_number: Optional[str] = None
    expiry_date: Optional[datetime] = None


class InventoryItem(InventoryItemBase):
    id: int
    product: Optional[Product] = None
    location: Optional[Location] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PickTaskItemCreate(BaseModel):
    product_id: int
    location_id: Optional[int] = None
    planned_qty: int = Field(..., gt=0)
    sort_order: Optional[int] = Field(0, ge=0)


class PicklistBase(BaseModel):
    picklist_no: Optional[str] = Field(None, max_length=64)
    order_no: Optional[str] = Field(None, max_length=64)
    customer: Optional[str] = Field(None, max_length=255)
    priority: Optional[int] = Field(5, ge=1, le=10)
    wave_no: Optional[str] = Field(None, max_length=64)
    delivery_address: Optional[str] = None
    planned_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_by: Optional[str] = Field(None, max_length=64)


class PicklistCreate(PicklistBase):
    items: List[PickTaskItemCreate] = Field(..., min_length=1)


class PicklistUpdate(BaseModel):
    priority: Optional[int] = None
    picker: Optional[str] = None
    delivery_address: Optional[str] = None
    planned_at: Optional[datetime] = None
    remark: Optional[str] = None


class PickBatchBase(BaseModel):
    batch_no: Optional[str] = Field(None, max_length=64)
    batch_type: Optional[str] = Field("normal", max_length=32)
    priority: Optional[int] = Field(5, ge=1, le=10)
    picker: Optional[str] = Field(None, max_length=64)
    planned_start_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_by: Optional[str] = Field(None, max_length=64)


class PickBatchCreate(PickBatchBase):
    picklist_ids: Optional[List[int]] = Field(None, description="要加入批次的拣货单ID列表")


class PickBatchUpdate(BaseModel):
    batch_type: Optional[str] = None
    priority: Optional[int] = None
    picker: Optional[str] = None
    planned_start_at: Optional[datetime] = None
    remark: Optional[str] = None


class PickBatchAssign(BaseModel):
    picker: str = Field(..., max_length=64)
    picklist_ids: Optional[List[int]] = Field(None, description="指定分配的拣货单ID，不填则分配批次下所有拣货单")


class PickTaskBase(BaseModel):
    pass


class PickTaskUpdate(BaseModel):
    picker: Optional[str] = None
    sort_order: Optional[int] = None


class PickTaskStart(BaseModel):
    picker: Optional[str] = Field(None, max_length=64)


class PickTaskComplete(BaseModel):
    picked_qty: int = Field(..., ge=0)
    short_qty: Optional[int] = Field(0, ge=0)
    damage_qty: Optional[int] = Field(0, ge=0)
    scan_code: Optional[str] = Field(None, max_length=64)
    exception_code: Optional[str] = Field(None, max_length=32)
    exception_note: Optional[str] = None


class PickTaskException(BaseModel):
    exception_code: str = Field(..., max_length=32)
    exception_note: Optional[str] = None
    picked_qty: Optional[int] = Field(0, ge=0)
    short_qty: Optional[int] = Field(0, ge=0)
    damage_qty: Optional[int] = Field(0, ge=0)


class PickTask(PickTaskBase):
    id: int
    task_no: str
    picklist_id: int
    location_id: int
    product_id: int
    product_sku: str
    product_name: str
    location_code: str
    lot_number: Optional[str] = None
    planned_qty: int
    picked_qty: int
    short_qty: int
    damage_qty: int
    status: TaskStatus
    picker: Optional[str] = None
    sort_order: int
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    exception_code: Optional[str] = None
    exception_note: Optional[str] = None
    scan_code: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Picklist(PicklistBase):
    id: int
    batch_id: Optional[int] = None
    status: PicklistStatus
    total_lines: int = 0
    total_qty: int = 0
    picked_qty: int = 0
    short_qty: int = 0
    picker: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tasks: List[PickTask] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PicklistSimple(BaseModel):
    id: int
    picklist_no: str
    order_no: Optional[str] = None
    customer: Optional[str] = None
    status: PicklistStatus
    priority: int
    total_lines: int = 0
    total_qty: int = 0
    picked_qty: int = 0

    class Config:
        from_attributes = True


class PickBatch(PickBatchBase):
    id: int
    batch_no: str
    status: BatchStatus
    total_orders: int = 0
    total_skus: int = 0
    total_qty: int = 0
    completed_qty: int = 0
    exception_count: int = 0
    actual_start_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    picklists: List[PicklistSimple] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PickBatchAddPicklists(BaseModel):
    picklist_ids: List[int] = Field(..., min_length=1)


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: dict
