from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import schemas, crud, models

router = APIRouter(prefix="/api/tasks", tags=["货位任务管理"])


@router.get("", summary="货位任务列表")
def list_pick_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[schemas.TaskStatus] = Query(None),
    picklist_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    picker: Optional[str] = Query(None, description="拣货员"),
    db: Session = Depends(get_db),
):
    items, total = crud.list_pick_tasks(db, page, page_size, status, picklist_id, location_id, picker)
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": [schemas.PickTask.model_validate(item).model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{task_id}", response_model=schemas.PickTask, summary="货位任务详情")
def get_pick_task(task_id: int, db: Session = Depends(get_db)):
    task = crud.get_pick_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="货位任务不存在")
    return task


@router.post("/{task_id}/assign", response_model=schemas.PickTask, summary="分配任务给拣货员")
def assign_task(
    task_id: int,
    data: schemas.PickTaskStart,
    db: Session = Depends(get_db),
):
    task = crud.get_pick_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="货位任务不存在")
    if task.status in [models.TaskStatus.COMPLETED, models.TaskStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.status.value}，无法分配")
    return crud.assign_task(db, task_id, data.picker)


@router.post("/{task_id}/start", response_model=schemas.PickTask, summary="开始拣货任务")
def start_task(
    task_id: int,
    data: Optional[schemas.PickTaskStart] = None,
    db: Session = Depends(get_db),
):
    task = crud.get_pick_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="货位任务不存在")
    if task.status in [models.TaskStatus.COMPLETED, models.TaskStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.status.value}，无法开始")
    if task.status == models.TaskStatus.EXCEPTION:
        raise HTTPException(status_code=400, detail="任务已标记异常，如需继续请先处理异常")
    picker = data.picker if data else None
    if not picker and not task.picker:
        raise HTTPException(status_code=400, detail="请指定拣货员或先分配任务")
    return crud.start_task(db, task_id, picker)


@router.post("/{task_id}/complete", response_model=schemas.PickTask, summary="完成拣货任务（状态回传）")
def complete_task(
    task_id: int,
    data: schemas.PickTaskComplete,
    db: Session = Depends(get_db),
):
    task = crud.get_pick_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="货位任务不存在")
    if task.status == models.TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务已完成，无需重复提交")
    if task.status == models.TaskStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="任务已取消")
    if data.picked_qty < 0:
        raise HTTPException(status_code=400, detail="拣货数量不能为负数")
    if (data.picked_qty + (data.short_qty or 0) + (data.damage_qty or 0)) > task.planned_qty:
        raise HTTPException(status_code=400, detail="拣货+短拣+破损数量之和不能超过计划数量")
    return crud.complete_task(db, task_id, data)


@router.post("/{task_id}/exception", response_model=schemas.PickTask, summary="上报任务异常")
def report_task_exception(
    task_id: int,
    data: schemas.PickTaskException,
    db: Session = Depends(get_db),
):
    task = crud.get_pick_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="货位任务不存在")
    if task.status == models.TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务已完成，无法上报异常")
    if task.status == models.TaskStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="任务已取消")
    return crud.report_task_exception(db, task_id, data)


@router.get("/by-no/{task_no}", response_model=schemas.PickTask, summary="通过任务编号查询")
def get_task_by_no(task_no: str, db: Session = Depends(get_db)):
    task = crud.get_task_by_no(db, task_no)
    if not task:
        raise HTTPException(status_code=404, detail="货位任务不存在")
    return task
