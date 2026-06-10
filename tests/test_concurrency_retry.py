import threading
import time
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from app.exceptions import DatabaseBusyError
from app import crud, schemas, models


def _make_operational_error_locked():
    return OperationalError(
        statement="BEGIN IMMEDIATE",
        params={},
        orig=Exception("database is locked"),
    )


def _make_operational_error_other():
    return OperationalError(
        statement="BEGIN IMMEDIATE",
        params={},
        orig=Exception("disk I/O error"),
    )


class TestDatabaseBusyError:
    def test_database_busy_error_default_values(self):
        err = DatabaseBusyError()
        assert "繁忙" in err.message
        assert err.retry_after_ms == 700
        d = err.to_dict()
        assert d["retry_after_ms"] == 700

    def test_database_busy_error_custom_values(self):
        err = DatabaseBusyError(message="自定义消息", retry_after_ms=1500)
        assert err.message == "自定义消息"
        assert err.retry_after_ms == 1500


class TestBeginImmediateRetry:
    def test_manual_tx_flag_tracks_nesting(self, db_session):
        db_session.rollback()
        db_session.info.pop("_manual_tx_active", None)
        assert "_manual_tx_active" not in db_session.info
        crud._begin_immediate(db_session)
        assert db_session.info["_manual_tx_active"] is True
        crud._begin_immediate(db_session)
        crud._begin_immediate(db_session)
        assert db_session.info["_manual_tx_active"] is True
        crud._end_manual_tx(db_session, commit=False)
        assert "_manual_tx_active" not in db_session.info

    @patch("app.crud.time.sleep", return_value=None)
    def test_retry_twice_then_succeed(self, mock_sleep, db_session):
        db_session.info.pop("_manual_tx_active", None)
        counts = {"n": 0}
        real_conn = db_session.connection()
        orig_execute = real_conn.execute

        def fake_execute(*args, **kwargs):
            stmt = args[0]
            stmt_str = str(stmt).upper() if hasattr(stmt, "__str__") else ""
            if "BEGIN IMMEDIATE" in stmt_str and counts["n"] < 2:
                counts["n"] += 1
                raise _make_operational_error_locked()
            counts["n"] += 1
            return orig_execute(*args, **kwargs)

        with patch.object(real_conn, "execute", side_effect=fake_execute):
            crud._begin_immediate(db_session)

        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 0.05
        assert mock_sleep.call_args_list[1][0][0] == 0.1
        assert counts["n"] == 3
        crud._end_manual_tx(db_session, commit=False)

    @patch("app.crud.time.sleep", return_value=None)
    def test_all_three_retries_fail_raises_database_busy_error(self, mock_sleep, db_session):
        db_session.info.pop("_manual_tx_active", None)
        real_conn = db_session.connection()
        orig_execute = real_conn.execute

        def always_locked(*args, **kwargs):
            stmt = args[0]
            stmt_str = str(stmt).upper() if hasattr(stmt, "__str__") else ""
            if "BEGIN IMMEDIATE" in stmt_str:
                raise _make_operational_error_locked()
            return orig_execute(*args, **kwargs)

        with patch.object(real_conn, "execute", side_effect=always_locked):
            with pytest.raises(DatabaseBusyError) as exc_info:
                crud._begin_immediate(db_session)

        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 0.05
        assert mock_sleep.call_args_list[1][0][0] == 0.1
        assert "重试3次" in exc_info.value.message
        assert exc_info.value.retry_after_ms > 0
        assert "_manual_tx_active" not in db_session.info

    @patch("app.crud.time.sleep", return_value=None)
    def test_first_attempt_locked_second_ok(self, mock_sleep, db_session):
        db_session.info.pop("_manual_tx_active", None)
        counts = {"n": 0}
        real_conn = db_session.connection()
        orig_execute = real_conn.execute

        def first_fail_execute(*args, **kwargs):
            stmt = args[0]
            stmt_str = str(stmt).upper() if hasattr(stmt, "__str__") else ""
            if "BEGIN IMMEDIATE" in stmt_str and counts["n"] == 0:
                counts["n"] += 1
                raise _make_operational_error_locked()
            counts["n"] += 1
            return orig_execute(*args, **kwargs)

        with patch.object(real_conn, "execute", side_effect=first_fail_execute):
            crud._begin_immediate(db_session)

        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(0.05)
        assert counts["n"] >= 2
        crud._end_manual_tx(db_session, commit=False)

    def test_non_lock_operational_error_reraised(self, db_session):
        db_session.info.pop("_manual_tx_active", None)
        real_conn = db_session.connection()
        orig_execute = real_conn.execute

        def broken_execute(*args, **kwargs):
            stmt = args[0]
            stmt_str = str(stmt).upper() if hasattr(stmt, "__str__") else ""
            if "BEGIN IMMEDIATE" in stmt_str:
                raise _make_operational_error_other()
            return orig_execute(*args, **kwargs)

        with patch.object(real_conn, "execute", side_effect=broken_execute):
            with pytest.raises(OperationalError):
                crud._begin_immediate(db_session)

        assert "_manual_tx_active" not in db_session.info

    def test_http_503_response_on_database_busy(self, app, client, seed_data):
        p1 = seed_data["products"][0].id
        picklist_resp = client.post(
            "/api/picklists",
            json={"order_no": "HTTP503", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        assert picklist_resp.status_code == 200
        task_id = 1

        def always_busy(*args, **kwargs):
            raise DatabaseBusyError(message="数据库繁忙，模拟锁冲突", retry_after_ms=350)

        with patch("app.routers.tasks.crud.complete_task", side_effect=always_busy):
            resp = client.post(
                f"/api/tasks/{task_id}/complete",
                json={"picked_qty": 1},
            )

        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == 503
        assert "繁忙" in body["message"] or "重试" in body["message"]
        assert body["data"]["retry_after_ms"] == 350
        assert "稍后重试" in body["data"]["suggestion"]
        assert "Retry-After" in resp.headers


class TestFinallyRollback:
    def test_create_picklist_invalid_product_rollsback_inventory(self, db_engine, seed_data):
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        db = SessionLocal()
        try:
            inv_before = (
                db.query(models.InventoryItem)
                .filter(models.InventoryItem.location_id == seed_data["locations"][0].id)
                .all()
            )
            inv_snapshot = {i.id: (i.available_qty, i.reserved_qty) for i in inv_before}

            bad_product_id = 999999999
            with pytest.raises(ValueError):
                crud.create_picklist(
                    db,
                    schemas.PicklistCreate(
                        order_no="RB1",
                        items=[
                            {"product_id": seed_data["products"][0].id, "planned_qty": 5},
                            {"product_id": bad_product_id, "planned_qty": 1},
                        ],
                    ),
                )

            assert "_manual_tx_active" not in db.info
            db.close()

            db2 = SessionLocal()
            try:
                for inv in db2.query(models.InventoryItem).filter(
                    models.InventoryItem.location_id == seed_data["locations"][0].id
                ).all():
                    orig = inv_snapshot.get(inv.id)
                    assert orig is not None
                    assert inv.available_qty == orig[0], f"库存 available_qty 未回滚: inv_id={inv.id}"
                    assert inv.reserved_qty == orig[1], f"库存 reserved_qty 未回滚: inv_id={inv.id}"
            finally:
                db2.close()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def test_create_picklist_no_inventory_rollsback_partial_reservation(self, db_engine, seed_data):
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        db = SessionLocal()
        try:
            p1 = seed_data["products"][0].id
            loc1 = seed_data["locations"][0].id
            inv = (
                db.query(models.InventoryItem)
                .filter_by(product_id=p1, location_id=loc1)
                .first()
            )
            qty_before = inv.available_qty
            reserved_before = inv.reserved_qty

            p3 = seed_data["products"][2].id

            original_find = crud.find_best_inventory_location

            def fail_second_call(*args, **kwargs):
                if args[1] == p3:
                    return None
                return original_find(*args, **kwargs)

            with patch.object(crud, "find_best_inventory_location", side_effect=fail_second_call):
                with pytest.raises(ValueError):
                    crud.create_picklist(
                        db,
                        schemas.PicklistCreate(
                            order_no="RB2",
                            items=[
                                {"product_id": p1, "location_id": loc1, "planned_qty": 3},
                                {"product_id": p3, "planned_qty": 5},
                            ],
                        ),
                    )

            assert "_manual_tx_active" not in db.info
            db.close()

            db2 = SessionLocal()
            try:
                inv_check = (
                    db2.query(models.InventoryItem)
                    .filter_by(product_id=p1, location_id=loc1)
                    .first()
                )
                assert inv_check.available_qty == qty_before
                assert inv_check.reserved_qty == reserved_before
            finally:
                db2.close()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def test_create_picklist_success_clean_state(self, db_engine, seed_data):
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        db = SessionLocal()
        try:
            p1 = seed_data["products"][0].id
            loc1 = seed_data["locations"][0].id
            pl = crud.create_picklist(
                db,
                schemas.PicklistCreate(
                    order_no="RBOK",
                    items=[{"product_id": p1, "location_id": loc1, "planned_qty": 2}],
                ),
            )
            assert pl.id is not None
            assert "_manual_tx_active" not in db.info
            pl2 = crud.create_picklist(
                db,
                schemas.PicklistCreate(
                    order_no="RBOK2",
                    items=[{"product_id": p1, "location_id": loc1, "planned_qty": 1}],
                ),
            )
            assert pl2.id is not None
            assert "_manual_tx_active" not in db.info
        finally:
            db.close()

    def test_complete_task_mocked_error_rollsback(self, db_engine, seed_data):
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        db = SessionLocal()
        try:
            p1 = seed_data["products"][0].id
            loc1 = seed_data["locations"][0].id

            pl = crud.create_picklist(
                db,
                schemas.PicklistCreate(
                    order_no="RB3",
                    items=[{"product_id": p1, "location_id": loc1, "planned_qty": 5}],
                ),
            )
            task = pl.tasks[0]
            task_id = task.id
            inv = (
                db.query(models.InventoryItem)
                .filter_by(product_id=p1, location_id=loc1)
                .first()
            )
            assert inv.reserved_qty == 5

            crud.start_task(db, task_id)
            db.close()

            db2 = SessionLocal()
            try:
                inv_after_start = (
                    db2.query(models.InventoryItem)
                    .filter_by(product_id=p1, location_id=loc1)
                    .first()
                )
                reserved_after_start = inv_after_start.reserved_qty
                task_start = db2.query(models.PickTask).filter_by(id=task_id).first()
                status_before = task_start.status

                with patch.object(
                    crud, "release_reserved_inventory", side_effect=RuntimeError("模拟内部异常")
                ):
                    with pytest.raises(RuntimeError):
                        crud.complete_task(
                            db2,
                            task_id,
                            schemas.PickTaskComplete(picked_qty=5),
                        )

                assert "_manual_tx_active" not in db2.info
                db2.close()

                db3 = SessionLocal()
                try:
                    inv_final = (
                        db3.query(models.InventoryItem)
                        .filter_by(product_id=p1, location_id=loc1)
                        .first()
                    )
                    assert inv_final.reserved_qty == reserved_after_start

                    task_final = db3.query(models.PickTask).filter_by(id=task_id).first()
                    assert task_final.status == status_before
                    assert task_final.picked_qty == 0
                finally:
                    db3.close()
            finally:
                try:
                    db2.close()
                except Exception:
                    pass
        finally:
            try:
                db.close()
            except Exception:
                pass

    def test_report_task_exception_mocked_error_rollsback(self, db_engine, seed_data):
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        db = SessionLocal()
        try:
            p1 = seed_data["products"][0].id
            loc1 = seed_data["locations"][0].id

            pl = crud.create_picklist(
                db,
                schemas.PicklistCreate(
                    order_no="RB4",
                    items=[{"product_id": p1, "location_id": loc1, "planned_qty": 2}],
                ),
            )
            task = pl.tasks[0]
            task_id = task.id
            inv_before = (
                db.query(models.InventoryItem)
                .filter_by(product_id=p1, location_id=loc1)
                .first()
            )
            reserved_before = inv_before.reserved_qty
            assert reserved_before == 2
            db.close()

            db2 = SessionLocal()
            try:
                with patch.object(
                    crud, "release_reserved_inventory", side_effect=RuntimeError("模拟上报异常失败")
                ):
                    with pytest.raises(RuntimeError):
                        crud.report_task_exception(
                            db2,
                            task_id,
                            schemas.PickTaskException(
                                exception_code="DAMAGE",
                                exception_note="货物损坏",
                                picked_qty=0,
                                short_qty=0,
                                damage_qty=2,
                            ),
                        )

                assert "_manual_tx_active" not in db2.info
                db2.close()

                db3 = SessionLocal()
                try:
                    task_final = db3.query(models.PickTask).filter_by(id=task_id).first()
                    assert task_final.status != models.TaskStatus.EXCEPTION

                    inv_final = (
                        db3.query(models.InventoryItem)
                        .filter_by(product_id=p1, location_id=loc1)
                        .first()
                    )
                    assert inv_final.reserved_qty == reserved_before
                finally:
                    db3.close()
            finally:
                try:
                    db2.close()
                except Exception:
                    pass
        finally:
            try:
                db.close()
            except Exception:
                pass
