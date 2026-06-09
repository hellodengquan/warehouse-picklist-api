from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime
from typing import Optional, List, Tuple
import uuid

from app import models, schemas


def generate_no(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:6].upper()
    return f"{prefix}{ts}{rand}"


def get_product(db: Session, product_id: int):
    return db.query(models.Product).filter(models.Product.id == product_id).first()


def get_product_by_sku(db: Session, sku: str):
    return db.query(models.Product).filter(models.Product.sku == sku).first()


def list_products(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    status: Optional[models.ProductStatus] = None,
) -> Tuple[List[models.Product], int]:
    query = db.query(models.Product)
    if keyword:
        query = query.filter(
            or_(
                models.Product.sku.contains(keyword),
                models.Product.name.contains(keyword),
                models.Product.barcode.contains(keyword) if models.Product.barcode else False
            )
        )
    if status:
        query = query.filter(models.Product.status == status)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def create_product(db: Session, obj_in: schemas.ProductCreate):
    db_obj = models.Product(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_product(db: Session, db_obj: models.Product, obj_in: schemas.ProductUpdate):
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_location(db: Session, location_id: int):
    return db.query(models.Location).filter(models.Location.id == location_id).first()


def get_location_by_code(db: Session, code: str):
    return db.query(models.Location).filter(models.Location.code == code).first()


def list_locations(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    zone: Optional[str] = None,
    status: Optional[models.LocationStatus] = None,
) -> Tuple[List[models.Location], int]:
    query = db.query(models.Location)
    if keyword:
        query = query.filter(models.Location.code.contains(keyword))
    if zone:
        query = query.filter(models.Location.zone == zone)
    if status:
        query = query.filter(models.Location.status == status)
    total = query.count()
    items = query.order_by(models.Location.code.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def create_location(db: Session, obj_in: schemas.LocationCreate):
    db_obj = models.Location(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_location(db: Session, db_obj: models.Location, obj_in: schemas.LocationUpdate):
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_inventory(db: Session, inventory_id: int):
    return db.query(models.InventoryItem).filter(models.InventoryItem.id == inventory_id).first()


def find_best_inventory_location(
    db: Session,
    product_id: int,
    required_qty: int,
    preferred_location_id: Optional[int] = None,
) -> Optional[models.InventoryItem]:
    query = db.query(models.InventoryItem).filter(
        models.InventoryItem.product_id == product_id,
        models.InventoryItem.available_qty > 0
    )
    if preferred_location_id:
        preferred = query.filter(models.InventoryItem.location_id == preferred_location_id).first()
        if preferred and preferred.available_qty >= required_qty:
            return preferred
    items = query.order_by(models.InventoryItem.available_qty.desc()).all()
    for item in items:
        if item.available_qty >= required_qty:
            return item
    return items[0] if items else None


def create_inventory(db: Session, obj_in: schemas.InventoryItemCreate):
    data = obj_in.model_dump()
    if "available_qty" not in data or data["available_qty"] is None:
        data["available_qty"] = data.get("quantity", 0)
    db_obj = models.InventoryItem(**data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_inventory_available(db: Session, inventory_id: int, delta: int):
    inv = get_inventory(db, inventory_id)
    if not inv:
        return None
    new_avail = inv.available_qty + delta
    new_reserved = inv.reserved_qty - delta
    if new_avail < 0:
        new_avail = 0
    if new_reserved < 0:
        new_reserved = 0
    inv.available_qty = new_avail
    inv.reserved_qty = new_reserved
    db.commit()
    db.refresh(inv)
    return inv


def reserve_inventory(db: Session, product_id: int, location_id: int, qty: int):
    inv = (
        db.query(models.InventoryItem)
        .filter(
            models.InventoryItem.product_id == product_id,
            models.InventoryItem.location_id == location_id,
        )
        .with_for_update()
        .first()
    )
    if not inv:
        return False
    if inv.available_qty < qty:
        return False
    inv.available_qty -= qty
    inv.reserved_qty += qty
    db.flush()
    return True


def release_reserved_inventory(db: Session, product_id: int, location_id: int, qty: int):
    inv = (
        db.query(models.InventoryItem)
        .filter(
            models.InventoryItem.product_id == product_id,
            models.InventoryItem.location_id == location_id,
        )
        .with_for_update()
        .first()
    )
    if not inv:
        return False
    release_qty = min(qty, inv.reserved_qty)
    inv.available_qty += release_qty
    inv.reserved_qty -= release_qty
    db.flush()
    return True


def create_picklist(db: Session, obj_in: schemas.PicklistCreate) -> models.Picklist:
    picklist_no = obj_in.picklist_no or generate_no("PL")
    picklist_data = obj_in.model_dump(exclude={"items"}, exclude_unset=True)
    picklist_data["picklist_no"] = picklist_no

    picklist = models.Picklist(**picklist_data)
    db.add(picklist)
    db.flush()

    total_lines = 0
    total_qty = 0

    for idx, item in enumerate(obj_in.items):
        product = get_product(db, item.product_id)
        if not product:
            raise ValueError(f"Product {item.product_id} not found")

        location_id = item.location_id
        inventory = None
        if location_id:
            inventory = db.query(models.InventoryItem).filter(
                models.InventoryItem.product_id == item.product_id,
                models.InventoryItem.location_id == location_id
            ).first()
        if not inventory:
            inventory = find_best_inventory_location(db, item.product_id, item.planned_qty, location_id)

        if not inventory:
            raise ValueError(f"No available inventory for product {product.sku}")

        location = get_location(db, inventory.location_id)

        task_no = generate_no("TK")
        task = models.PickTask(
            task_no=task_no,
            picklist_id=picklist.id,
            location_id=location.id,
            product_id=product.id,
            product_sku=product.sku,
            product_name=product.name,
            location_code=location.code,
            lot_number=inventory.lot_number,
            planned_qty=item.planned_qty,
            sort_order=item.sort_order or idx,
        )
        db.add(task)
        reserve_inventory(db, product.id, location.id, item.planned_qty)

        total_lines += 1
        total_qty += item.planned_qty

    picklist.total_lines = total_lines
    picklist.total_qty = total_qty
    db.commit()
    db.refresh(picklist)
    return picklist


def get_picklist(db: Session, picklist_id: int):
    return db.query(models.Picklist).filter(models.Picklist.id == picklist_id).first()


def list_picklists(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[models.PicklistStatus] = None,
    batch_id: Optional[int] = None,
    keyword: Optional[str] = None,
    picker: Optional[str] = None,
) -> Tuple[List[models.Picklist], int]:
    query = db.query(models.Picklist)
    if status:
        query = query.filter(models.Picklist.status == status)
    if batch_id is not None:
        query = query.filter(models.Picklist.batch_id == batch_id)
    if keyword:
        query = query.filter(
            or_(
                models.Picklist.picklist_no.contains(keyword),
                models.Picklist.order_no.contains(keyword) if models.Picklist.order_no else False
            )
        )
    if picker:
        query = query.filter(models.Picklist.picker == picker)
    total = query.count()
    items = query.order_by(models.Picklist.priority.desc(), models.Picklist.created_at.asc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def update_picklist_status(db: Session, picklist_id: int):
    picklist = get_picklist(db, picklist_id)
    if not picklist:
        return
    tasks = picklist.tasks
    if not tasks:
        return

    all_completed = all(t.status == models.TaskStatus.COMPLETED for t in tasks)
    any_exception = any(t.status == models.TaskStatus.EXCEPTION for t in tasks)
    any_picking = any(t.status in [models.TaskStatus.PICKING, models.TaskStatus.ASSIGNED] for t in tasks)
    all_pending = all(t.status == models.TaskStatus.PENDING for t in tasks)

    total_picked = sum(t.picked_qty for t in tasks)
    total_short = sum(t.short_qty for t in tasks)

    picklist.picked_qty = total_picked
    picklist.short_qty = total_short

    if all_completed and total_short == 0:
        picklist.status = models.PicklistStatus.COMPLETED
        if not picklist.completed_at:
            picklist.completed_at = datetime.now()
    elif all_completed and total_short > 0:
        picklist.status = models.PicklistStatus.PARTIAL
        if not picklist.completed_at:
            picklist.completed_at = datetime.now()
    elif any_picking or any_exception:
        picklist.status = models.PicklistStatus.IN_PROGRESS
        if not picklist.started_at:
            picklist.started_at = datetime.now()
    elif all_pending:
        picklist.status = models.PicklistStatus.PENDING

    db.commit()
    db.refresh(picklist)

    if picklist.batch_id:
        update_batch_status(db, picklist.batch_id)


def get_pick_task(db: Session, task_id: int):
    return db.query(models.PickTask).filter(models.PickTask.id == task_id).first()


def get_task_by_no(db: Session, task_no: str):
    return db.query(models.PickTask).filter(models.PickTask.task_no == task_no).first()


def list_pick_tasks(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[models.TaskStatus] = None,
    picklist_id: Optional[int] = None,
    location_id: Optional[int] = None,
    picker: Optional[str] = None,
) -> Tuple[List[models.PickTask], int]:
    query = db.query(models.PickTask)
    if status:
        query = query.filter(models.PickTask.status == status)
    if picklist_id:
        query = query.filter(models.PickTask.picklist_id == picklist_id)
    if location_id:
        query = query.filter(models.PickTask.location_id == location_id)
    if picker:
        query = query.filter(models.PickTask.picker == picker)
    total = query.count()
    items = query.order_by(models.PickTask.sort_order.asc(), models.PickTask.id.asc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def assign_task(db: Session, task_id: int, picker: str):
    task = get_pick_task(db, task_id)
    if not task:
        return None
    task.picker = picker
    task.status = models.TaskStatus.ASSIGNED
    task.assigned_at = datetime.now()
    db.commit()
    db.refresh(task)
    update_picklist_status(db, task.picklist_id)
    return task


def start_task(db: Session, task_id: int, picker: Optional[str] = None):
    task = get_pick_task(db, task_id)
    if not task:
        return None
    if picker:
        task.picker = picker
    task.status = models.TaskStatus.PICKING
    task.started_at = datetime.now()
    if not task.assigned_at:
        task.assigned_at = datetime.now()
    db.commit()
    db.refresh(task)
    update_picklist_status(db, task.picklist_id)
    return task


def complete_task(db: Session, task_id: int, data: schemas.PickTaskComplete):
    task = (
        db.query(models.PickTask)
        .filter(models.PickTask.id == task_id)
        .with_for_update()
        .first()
    )
    if not task:
        return None

    if task.status in [models.TaskStatus.COMPLETED, models.TaskStatus.CANCELLED]:
        db.commit()
        return task
    if task.status == models.TaskStatus.EXCEPTION:
        db.commit()
        return task

    picked = data.picked_qty
    short = data.short_qty or 0
    damage = data.damage_qty or 0
    total = picked + short + damage

    if total != task.planned_qty and short == 0:
        short = task.planned_qty - picked - damage
        if short < 0:
            short = 0

    task.picked_qty = picked
    task.short_qty = short
    task.damage_qty = damage
    task.scan_code = data.scan_code
    task.completed_at = datetime.now()

    if short > 0 or damage > 0:
        task.status = models.TaskStatus.EXCEPTION
        task.exception_code = data.exception_code or ("SHORT" if short > 0 else "DAMAGE")
        task.exception_note = data.exception_note
    else:
        task.status = models.TaskStatus.COMPLETED
        task.exception_code = None
        task.exception_note = None

    release_reserved_inventory(db, task.product_id, task.location_id, task.planned_qty)

    db.flush()
    db.commit()
    db.refresh(task)
    update_picklist_status(db, task.picklist_id)
    return task


def report_task_exception(db: Session, task_id: int, data: schemas.PickTaskException):
    task = (
        db.query(models.PickTask)
        .filter(models.PickTask.id == task_id)
        .with_for_update()
        .first()
    )
    if not task:
        return None
    if task.status in [models.TaskStatus.COMPLETED, models.TaskStatus.CANCELLED]:
        db.commit()
        return task

    task.status = models.TaskStatus.EXCEPTION
    task.exception_code = data.exception_code
    task.exception_note = data.exception_note
    task.picked_qty = data.picked_qty or 0
    task.short_qty = data.short_qty or 0
    task.damage_qty = data.damage_qty or 0
    task.completed_at = datetime.now()

    release_reserved_inventory(db, task.product_id, task.location_id, task.planned_qty)

    db.flush()
    db.commit()
    db.refresh(task)
    update_picklist_status(db, task.picklist_id)
    return task


def create_pick_batch(db: Session, obj_in: schemas.PickBatchCreate) -> models.PickBatch:
    batch_no = obj_in.batch_no or generate_no("PB")
    batch_data = obj_in.model_dump(exclude={"picklist_ids"}, exclude_unset=True)
    batch_data["batch_no"] = batch_no

    batch = models.PickBatch(**batch_data)
    db.add(batch)
    db.flush()

    total_orders = 0
    total_skus = 0
    total_qty = 0

    picklist_ids = obj_in.picklist_ids or []
    for pl_id in picklist_ids:
        picklist = get_picklist(db, pl_id)
        if picklist and not picklist.batch_id:
            picklist.batch_id = batch.id
            total_orders += 1
            total_skus += picklist.total_lines
            total_qty += picklist.total_qty
            if obj_in.picker:
                picklist.picker = obj_in.picker
                for task in picklist.tasks:
                    task.picker = obj_in.picker
                    task.status = models.TaskStatus.ASSIGNED
                    task.assigned_at = datetime.now()

    batch.total_orders = total_orders
    batch.total_skus = total_skus
    batch.total_qty = total_qty

    if total_orders > 0 and obj_in.picker:
        batch.status = models.BatchStatus.ASSIGNED

    db.commit()
    db.refresh(batch)
    return batch


def get_pick_batch(db: Session, batch_id: int):
    return db.query(models.PickBatch).filter(models.PickBatch.id == batch_id).first()


def list_pick_batches(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[models.BatchStatus] = None,
    picker: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Tuple[List[models.PickBatch], int]:
    query = db.query(models.PickBatch)
    if status:
        query = query.filter(models.PickBatch.status == status)
    if picker:
        query = query.filter(models.PickBatch.picker == picker)
    if keyword:
        query = query.filter(models.PickBatch.batch_no.contains(keyword))
    total = query.count()
    items = query.order_by(models.PickBatch.priority.desc(), models.PickBatch.created_at.asc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def add_picklists_to_batch(db: Session, batch_id: int, picklist_ids: List[int]):
    batch = get_pick_batch(db, batch_id)
    if not batch:
        return None

    added = 0
    for pl_id in picklist_ids:
        picklist = get_picklist(db, pl_id)
        if picklist and not picklist.batch_id:
            picklist.batch_id = batch.id
            batch.total_orders += 1
            batch.total_skus += picklist.total_lines
            batch.total_qty += picklist.total_qty
            if batch.picker:
                picklist.picker = batch.picker
                for task in picklist.tasks:
                    task.picker = batch.picker
                    if task.status == models.TaskStatus.PENDING:
                        task.status = models.TaskStatus.ASSIGNED
                        task.assigned_at = datetime.now()
            added += 1

    if added > 0 and batch.status == models.BatchStatus.PENDING and batch.picker:
        batch.status = models.BatchStatus.ASSIGNED

    db.commit()
    db.refresh(batch)
    return batch


def assign_batch(db: Session, batch_id: int, data: schemas.PickBatchAssign):
    batch = get_pick_batch(db, batch_id)
    if not batch:
        return None

    picklist_ids = data.picklist_ids or [pl.id for pl in batch.picklists]

    for pl_id in picklist_ids:
        picklist = get_picklist(db, pl_id)
        if picklist and picklist.batch_id == batch_id:
            picklist.picker = data.picker
            for task in picklist.tasks:
                if task.status == models.TaskStatus.PENDING:
                    task.picker = data.picker
                    task.status = models.TaskStatus.ASSIGNED
                    task.assigned_at = datetime.now()

    batch.picker = data.picker
    if batch.status == models.BatchStatus.PENDING:
        batch.status = models.BatchStatus.ASSIGNED

    db.commit()
    db.refresh(batch)
    return batch


def start_batch(db: Session, batch_id: int, picker: Optional[str] = None):
    batch = get_pick_batch(db, batch_id)
    if not batch:
        return None

    if picker:
        batch.picker = picker

    batch.status = models.BatchStatus.PICKING
    batch.actual_start_at = datetime.now()

    for picklist in batch.picklists:
        if picker:
            picklist.picker = picker
        picklist.status = models.PicklistStatus.IN_PROGRESS
        if not picklist.started_at:
            picklist.started_at = datetime.now()
        for task in picklist.tasks:
            if task.status == models.TaskStatus.PENDING or task.status == models.TaskStatus.ASSIGNED:
                if picker:
                    task.picker = picker
                task.status = models.TaskStatus.PICKING
                if not task.started_at:
                    task.started_at = datetime.now()

    db.commit()
    db.refresh(batch)
    return batch


def update_batch_status(db: Session, batch_id: int):
    batch = get_pick_batch(db, batch_id)
    if not batch:
        return

    picklists = batch.picklists
    if not picklists:
        return

    completed_qty = 0
    exception_count = 0
    all_done = True

    for pl in picklists:
        completed_qty += pl.picked_qty
        for task in pl.tasks:
            if task.status == models.TaskStatus.EXCEPTION:
                exception_count += 1
            if task.status not in [models.TaskStatus.COMPLETED, models.TaskStatus.EXCEPTION, models.TaskStatus.CANCELLED]:
                all_done = False

    batch.completed_qty = completed_qty
    batch.exception_count = exception_count

    if all_done:
        batch.status = models.BatchStatus.COMPLETED
        batch.completed_at = datetime.now()
    elif batch.status == models.BatchStatus.ASSIGNED and any(
        pl.status in [models.PicklistStatus.IN_PROGRESS, models.PicklistStatus.COMPLETED, models.PicklistStatus.PARTIAL]
        for pl in picklists
    ):
        batch.status = models.BatchStatus.PICKING
        if not batch.actual_start_at:
            batch.actual_start_at = datetime.now()

    db.commit()
    db.refresh(batch)
