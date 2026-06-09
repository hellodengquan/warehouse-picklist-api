class TestBatchCreate:
    def test_create_batch_empty(self, client):
        resp = client.post(
            "/api/batches",
            json={
                "batch_type": "normal",
                "priority": 5,
                "remark": "空批次",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["total_orders"] == 0
        assert data["batch_no"].startswith("PB")

    def test_create_batch_with_picklists(self, client, seed_data):
        p1 = seed_data["products"][0].id
        p2 = seed_data["products"][1].id
        r1 = client.post(
            "/api/picklists",
            json={"order_no": "BATCH-PL1", "items": [{"product_id": p1, "planned_qty": 2}]},
        )
        r2 = client.post(
            "/api/picklists",
            json={"order_no": "BATCH-PL2", "items": [{"product_id": p2, "planned_qty": 3}]},
        )
        pl1_id = r1.json()["id"]
        pl2_id = r2.json()["id"]

        resp = client.post(
            "/api/batches",
            json={
                "batch_type": "urgent",
                "priority": 9,
                "picker": "batchpicker",
                "remark": "带拣货单的批次",
                "created_by": "tester",
                "picklist_ids": [pl1_id, pl2_id],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "assigned"
        assert data["picker"] == "batchpicker"
        assert data["total_orders"] == 2
        assert data["total_skus"] == 2
        assert data["total_qty"] == 5
        assert len(data["picklists"]) == 2

    def test_create_batch_with_invalid_picklist(self, client, seed_data):
        resp = client.post(
            "/api/batches",
            json={
                "remark": "无效拣货单",
                "picklist_ids": [99999],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["total_orders"] == 0


class TestBatchQuery:
    def test_get_batch_detail(self, client):
        client.post("/api/batches", json={"remark": "detail batch"})
        resp = client.get("/api/batches/1")
        assert resp.status_code == 200
        assert resp.json()["remark"] == "detail batch"

    def test_get_batch_not_found(self, client):
        resp = client.get("/api/batches/99999")
        assert resp.status_code == 404

    def test_list_batches(self, client):
        for i in range(3):
            client.post("/api/batches", json={"remark": f"b{i}"})
        resp = client.get("/api/batches")
        body = resp.json()
        assert body["data"]["total"] == 3
        assert len(body["data"]["items"]) == 3

    def test_list_batches_filter_status(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post("/api/batches", json={})
        resp_pending = client.get("/api/batches?status=pending")
        assert resp_pending.json()["data"]["total"] == 1
        resp_completed = client.get("/api/batches?status=completed")
        assert resp_completed.json()["data"]["total"] == 0


class TestBatchUpdate:
    def test_update_batch(self, client):
        client.post("/api/batches", json={})
        resp = client.put(
            "/api/batches/1",
            json={"remark": "修改批次", "priority": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["remark"] == "修改批次"
        assert resp.json()["priority"] == 10

    def test_update_batch_not_found(self, client):
        resp = client.put("/api/batches/99999", json={"remark": "x"})
        assert resp.status_code == 404


class TestBatchAddPicklists:
    def test_add_picklists_success(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post("/api/batches", json={})
        r = client.post(
            "/api/picklists",
            json={"order_no": "ADDPL", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        pl_id = r.json()["id"]

        resp = client.post(
            "/api/batches/1/picklists",
            json={"picklist_ids": [pl_id]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 1
        assert len(data["picklists"]) == 1

    def test_add_picklists_batch_not_found(self, client, seed_data):
        p1 = seed_data["products"][0].id
        r = client.post(
            "/api/picklists",
            json={"order_no": "NF", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.post(
            "/api/batches/99999/picklists",
            json={"picklist_ids": [r.json()["id"]]},
        )
        assert resp.status_code == 404

    def test_add_already_batched_picklist(self, client, seed_data):
        p1 = seed_data["products"][0].id
        r = client.post(
            "/api/picklists",
            json={"order_no": "DUP", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        pl_id = r.json()["id"]
        client.post("/api/batches", json={"picklist_ids": [pl_id]})
        client.post("/api/batches", json={})
        resp = client.post(
            "/api/batches/2/picklists",
            json={"picklist_ids": [pl_id]},
        )
        assert resp.status_code == 200
        assert resp.json()["total_orders"] == 0


class TestBatchAssignAndStart:
    def test_assign_batch_success(self, client, seed_data):
        p1 = seed_data["products"][0].id
        r1 = client.post(
            "/api/picklists",
            json={"order_no": "A1", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        r2 = client.post(
            "/api/picklists",
            json={"order_no": "A2", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        client.post(
            "/api/batches",
            json={"picklist_ids": [r1.json()["id"], r2.json()["id"]]},
        )
        resp = client.post(
            "/api/batches/1/assign",
            json={"picker": "assign001"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "assigned"
        assert resp.json()["picker"] == "assign001"

    def test_assign_batch_not_found(self, client):
        resp = client.post(
            "/api/batches/99999/assign",
            json={"picker": "x"},
        )
        assert resp.status_code == 404

    def test_start_batch_success(self, client, seed_data):
        p1 = seed_data["products"][0].id
        r = client.post(
            "/api/picklists",
            json={"order_no": "START-PL", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        client.post(
            "/api/batches",
            json={"picklist_ids": [r.json()["id"]]},
        )
        resp = client.post("/api/batches/1/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "picking"
        assert data["actual_start_at"] is not None

    def test_start_completed_batch(self, client):
        pass

    def test_start_not_found_batch(self, client):
        resp = client.post("/api/batches/99999/start")
        assert resp.status_code == 404

    def test_start_completed_batch_fails(self, client, seed_data):
        p1 = seed_data["products"][0].id
        r = client.post(
            "/api/picklists",
            json={"order_no": "COMPL-PL", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        batch_id = client.post(
            "/api/batches",
            json={"picklist_ids": [r.json()["id"]]},
        ).json()["id"]
        pl = client.get(f"/api/picklists/{r.json()['id']}").json()
        task_id = pl["tasks"][0]["id"]
        client.post(f"/api/tasks/{task_id}/start")
        client.post(
            f"/api/tasks/{task_id}/complete",
            json={"picked_qty": 1},
        )

        resp = client.post(f"/api/batches/{batch_id}/start")
        assert resp.status_code == 400
