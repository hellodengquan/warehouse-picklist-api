import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.database import SessionLocal
from app import models


class TestTaskQuery:
    def test_list_tasks_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_get_task_not_found(self, client):
        resp = client.get("/api/tasks/99999")
        assert resp.status_code == 404

    def test_get_task_by_no_not_found(self, client):
        resp = client.get("/api/tasks/by-no/TK-NOT-EXIST-99999")
        assert resp.status_code == 404

    def test_list_tasks_filter_by_picklist(self, client, seed_data):
        p1 = seed_data["products"][0].id
        p2 = seed_data["products"][1].id
        client.post(
            "/api/picklists",
            json={
                "order_no": "FL1",
                "items": [
                    {"product_id": p1, "planned_qty": 1},
                    {"product_id": p2, "planned_qty": 1},
                ],
            },
        )
        resp = client.get("/api/tasks?picklist_id=1")
        body = resp.json()
        assert body["data"]["total"] == 2

    def test_list_tasks_filter_by_status(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "FS", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.get("/api/tasks?status=pending")
        assert resp.json()["data"]["total"] == 1
        resp2 = client.get("/api/tasks?status=completed")
        assert resp2.json()["data"]["total"] == 0

    def test_get_task_detail(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "DT", "items": [{"product_id": p1, "planned_qty": 3}]},
        )
        resp = client.get("/api/tasks/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["planned_qty"] == 3
        assert data["picked_qty"] == 0
        assert data["status"] == "pending"


class TestTaskAssign:
    def test_assign_task_success(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "AS", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.post(
            "/api/tasks/1/assign",
            json={"picker": "picker-assign"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "assigned"
        assert data["picker"] == "picker-assign"
        assert data["assigned_at"] is not None

    def test_assign_task_not_found(self, client):
        resp = client.post("/api/tasks/99999/assign", json={"picker": "x"})
        assert resp.status_code == 404

    def test_assign_completed_task_should_fail(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "AC", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        client.post("/api/tasks/1/start")
        client.post("/api/tasks/1/complete", json={"picked_qty": 1})
        resp = client.post(
            "/api/tasks/1/assign",
            json={"picker": "re-assign"},
        )
        assert resp.status_code == 400


class TestTaskStart:
    def test_start_task_success(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "ST", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.post(
            "/api/tasks/1/start",
            json={"picker": "picker-start"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "picking"
        assert data["picker"] == "picker-start"
        assert data["started_at"] is not None

    def test_start_task_without_picker_when_not_assigned(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "SP", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.post("/api/tasks/1/start")
        assert resp.status_code == 400

    def test_start_already_completed(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "SC", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p1"})
        client.post("/api/tasks/1/complete", json={"picked_qty": 1})
        resp = client.post("/api/tasks/1/start", json={"picker": "p2"})
        assert resp.status_code == 400

    def test_start_exception_task_should_fail(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "SE", "items": [{"product_id": p1, "planned_qty": 2}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        client.post(
            "/api/tasks/1/exception",
            json={
                "exception_code": "SHORT",
                "exception_note": "缺货",
                "picked_qty": 1,
                "short_qty": 1,
            },
        )
        resp = client.post("/api/tasks/1/start", json={"picker": "p"})
        assert resp.status_code == 400


class TestTaskComplete:
    def test_complete_task_normal(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "CN", "items": [{"product_id": p1, "planned_qty": 5}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "picker-norm"})
        resp = client.post(
            "/api/tasks/1/complete",
            json={
                "picked_qty": 5,
                "short_qty": 0,
                "damage_qty": 0,
                "scan_code": "0000000000",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["picked_qty"] == 5
        assert data["short_qty"] == 0
        assert data["scan_code"] == "0000000000"
        assert data["completed_at"] is not None

    def test_complete_task_auto_calc_short(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "AS", "items": [{"product_id": p1, "planned_qty": 10}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        resp = client.post(
            "/api/tasks/1/complete",
            json={"picked_qty": 7},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "exception"
        assert data["picked_qty"] == 7
        assert data["short_qty"] == 3
        assert data["exception_code"] == "SHORT"

    def test_complete_with_damage(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "CD", "items": [{"product_id": p1, "planned_qty": 4}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        resp = client.post(
            "/api/tasks/1/complete",
            json={
                "picked_qty": 3,
                "short_qty": 0,
                "damage_qty": 1,
                "exception_code": "DAMAGE",
                "exception_note": "外箱破损",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "exception"
        assert data["damage_qty"] == 1
        assert data["exception_code"] == "DAMAGE"
        assert data["exception_note"] == "外箱破损"

    def test_complete_already_completed_fails(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "RPT", "items": [{"product_id": p1, "planned_qty": 2}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        client.post("/api/tasks/1/complete", json={"picked_qty": 2})
        resp = client.post("/api/tasks/1/complete", json={"picked_qty": 2})
        assert resp.status_code == 400
        assert "已完成" in resp.json()["detail"]

    def test_complete_not_found(self, client):
        resp = client.post("/api/tasks/99999/complete", json={"picked_qty": 1})
        assert resp.status_code == 404

    def test_complete_negative_picked_rejected_by_schema(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "NEG", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        resp = client.post(
            "/api/tasks/1/complete",
            json={"picked_qty": -1},
        )
        assert resp.status_code == 422

    def test_complete_over_planned_qty(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "OVER", "items": [{"product_id": p1, "planned_qty": 2}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        resp = client.post(
            "/api/tasks/1/complete",
            json={"picked_qty": 5},
        )
        assert resp.status_code == 400

    def test_complete_picklist_status_updates(self, client, seed_data):
        p1 = seed_data["products"][0].id
        p2 = seed_data["products"][1].id
        pl_resp = client.post(
            "/api/picklists",
            json={
                "order_no": "STAT",
                "items": [
                    {"product_id": p1, "planned_qty": 2},
                    {"product_id": p2, "planned_qty": 3},
                ],
            },
        )
        pl_id = pl_resp.json()["id"]
        client.post("/api/batches", json={"picklist_ids": [pl_id]})
        client.post("/api/batches/1/start", json={"picker": "picker-status"})
        client.post("/api/tasks/1/complete", json={"picked_qty": 2})
        pl = client.get(f"/api/picklists/{pl_id}").json()
        assert pl["status"] == "in_progress"
        assert pl["picked_qty"] == 2
        client.post("/api/tasks/2/complete", json={"picked_qty": 3})
        pl2 = client.get(f"/api/picklists/{pl_id}").json()
        assert pl2["status"] == "completed"
        assert pl2["picked_qty"] == 5
        assert pl2["completed_at"] is not None


class TestTaskException:
    def test_report_exception(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "EX", "items": [{"product_id": p1, "planned_qty": 5}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        resp = client.post(
            "/api/tasks/1/exception",
            json={
                "exception_code": "OUT_OF_STOCK",
                "exception_note": "盘点后发现实物缺失",
                "picked_qty": 0,
                "short_qty": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "exception"
        assert data["exception_code"] == "OUT_OF_STOCK"
        assert data["exception_note"] == "盘点后发现实物缺失"
        assert data["short_qty"] == 5

    def test_exception_on_completed_task(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "EC", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        client.post("/api/tasks/1/start", json={"picker": "p"})
        client.post("/api/tasks/1/complete", json={"picked_qty": 1})
        resp = client.post(
            "/api/tasks/1/exception",
            json={"exception_code": "OTHER", "picked_qty": 0, "short_qty": 1},
        )
        assert resp.status_code == 400

    def test_exception_not_found(self, client):
        resp = client.post(
            "/api/tasks/99999/exception",
            json={"exception_code": "X"},
        )
        assert resp.status_code == 404


class TestTaskConcurrency:
    def test_concurrent_complete_same_task_race_protected(self, app, seed_data):
        from fastapi.testclient import TestClient
        import random

        with TestClient(app) as client:
            p1 = seed_data["products"][0].id
            client.post(
                "/api/picklists",
                json={"order_no": "CONC", "items": [{"product_id": p1, "planned_qty": 10}]},
            )
            client.post("/api/tasks/1/start", json={"picker": "p-conc"})

        task_id = 1
        results = []
        errors = []
        exceptions = []

        def worker(i):
            try:
                from fastapi.testclient import TestClient
                with TestClient(app) as c:
                    resp = c.post(
                        f"/api/tasks/{task_id}/complete",
                        json={"picked_qty": 10, "short_qty": 0},
                    )
                    return (i, resp.status_code, resp.json())
            except Exception as e:
                exceptions.append(str(e))
                return (i, 0, {"error": str(e)})

        threads = []
        for i in range(5):
            t = threading.Thread(target=lambda idx=i: results.append(worker(idx)))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            final_task = client.get(f"/api/tasks/{task_id}").json()

        success_count = sum(1 for r in results if r and r[1] == 200)
        repeat_blocked = sum(1 for r in results if r and r[1] == 400)

        assert final_task["status"] == "completed"
        assert final_task["picked_qty"] == 10
        assert success_count >= 1
        assert repeat_blocked >= 1

    def test_concurrent_inventory_reservation(self, app, seed_data):
        from fastapi.testclient import TestClient
        from app.database import SessionLocal as TSL
        from app import models

        db = TSL()
        inv = (
            db.query(models.InventoryItem)
            .filter(
                models.InventoryItem.product_id == seed_data["products"][0].id,
                models.InventoryItem.location_id == seed_data["locations"][0].id,
            )
            .first()
        )
        initial_available = inv.available_qty
        inv_id = inv.id
        db.close()

        results = []
        errors = []

        def make_picklist(worker_id):
            try:
                from fastapi.testclient import TestClient
                with TestClient(app) as c:
                    resp = c.post(
                        "/api/picklists",
                        json={
                            "order_no": f"CONC-INV-{worker_id}",
                            "items": [
                                {
                                    "product_id": seed_data["products"][0].id,
                                    "planned_qty": 5,
                                    "location_id": seed_data["locations"][0].id,
                                }
                            ],
                        },
                    )
                    return (worker_id, resp.status_code, resp.json())
            except Exception as e:
                return (worker_id, 0, {"error": str(e)})

        threads = []
        for i in range(5):
            t = threading.Thread(target=lambda idx=i: results.append(make_picklist(idx)))
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=30)

        db = TSL()
        final_inv = db.query(models.InventoryItem).filter(models.InventoryItem.id == inv_id).first()
        final_available = final_inv.available_qty
        final_reserved = final_inv.reserved_qty
        db.close()

        ok_responses = [r for r in results if r and r[1] == 200]
        assert len(ok_responses) >= 1
        assert final_available + final_reserved == initial_available

    def test_batch_status_propagated_after_task_completions(self, client, seed_data):
        p1 = seed_data["products"][0].id
        p2 = seed_data["products"][1].id
        r = client.post(
            "/api/picklists",
            json={
                "order_no": "PROP",
                "items": [
                    {"product_id": p1, "planned_qty": 1},
                    {"product_id": p2, "planned_qty": 1},
                ],
            },
        )
        pl_id = r.json()["id"]
        client.post("/api/batches", json={"picklist_ids": [pl_id]})
        client.post("/api/batches/1/start")

        batch_before = client.get("/api/batches/1").json()
        assert batch_before["status"] == "picking"

        client.post("/api/tasks/1/complete", json={"picked_qty": 1})
        client.post("/api/tasks/2/complete", json={"picked_qty": 1})

        batch_after = client.get("/api/batches/1").json()
        assert batch_after["status"] == "completed"
        assert batch_after["completed_qty"] == 2
        assert batch_after["completed_at"] is not None
        assert batch_after["exception_count"] == 0
