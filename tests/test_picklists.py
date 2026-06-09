class TestPicklistCreate:
    def test_create_picklist_success_single_item(self, client, seed_data):
        p1_id = seed_data["products"][0].id
        payload = {
            "order_no": "TEST-0001",
            "customer": "测试客户A",
            "priority": 7,
            "delivery_address": "测试地址",
            "created_by": "tester",
            "items": [
                {"product_id": p1_id, "planned_qty": 5, "sort_order": 1},
            ],
        }
        resp = client.post("/api/picklists", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["order_no"] == "TEST-0001"
        assert data["status"] == "pending"
        assert data["total_lines"] == 1
        assert data["total_qty"] == 5
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["planned_qty"] == 5
        assert data["tasks"][0]["location_code"] in ["A-01-01-01", "A-01-01-02"]

    def test_create_picklist_multi_items(self, client, seed_data):
        products = seed_data["products"]
        payload = {
            "order_no": "TEST-0002",
            "customer": "多商品客户",
            "items": [
                {"product_id": products[0].id, "planned_qty": 2},
                {"product_id": products[1].id, "planned_qty": 3},
                {"product_id": products[2].id, "planned_qty": 1},
            ],
        }
        resp = client.post("/api/picklists", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_lines"] == 3
        assert data["total_qty"] == 6
        assert len(data["tasks"]) == 3
        task_skus = {t["product_sku"] for t in data["tasks"]}
        assert task_skus == {"SKU001", "SKU002", "SKU003"}

    def test_create_picklist_auto_allocate_location(self, client, seed_data):
        p1 = seed_data["products"][0]
        payload = {
            "order_no": "TEST-AUTOLOC",
            "items": [{"product_id": p1.id, "planned_qty": 3}],
        }
        resp = client.post("/api/picklists", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        task = data["tasks"][0]
        assert task["location_code"] in ["A-01-01-01", "A-01-01-02"]
        assert task["product_sku"] == "SKU001"

    def test_create_picklist_invalid_product(self, client, seed_data):
        payload = {
            "order_no": "TEST-ERR01",
            "items": [{"product_id": 999999, "planned_qty": 1}],
        }
        resp = client.post("/api/picklists", json=payload)
        assert resp.status_code == 400

    def test_create_picklist_empty_items(self, client):
        payload = {
            "order_no": "TEST-EMPTY",
            "items": [],
        }
        resp = client.post("/api/picklists", json=payload)
        assert resp.status_code == 422

    def test_create_picklist_zero_qty(self, client, seed_data):
        p1 = seed_data["products"][0].id
        payload = {
            "order_no": "TEST-ZERO",
            "items": [{"product_id": p1, "planned_qty": 0}],
        }
        resp = client.post("/api/picklists", json=payload)
        assert resp.status_code == 422

    def test_create_picklist_inventory_consumed(self, client, seed_data, db_session):
        from app import crud
        inv_before = (
            db_session.query(crud.models.InventoryItem)
            .filter(
                crud.models.InventoryItem.product_id == seed_data["products"][0].id,
                crud.models.InventoryItem.location_id == seed_data["locations"][0].id,
            )
            .first()
        )
        avail_before = inv_before.available_qty
        reserved_before = inv_before.reserved_qty

        p1_id = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={
                "order_no": "TEST-INV",
                "items": [
                    {"product_id": p1_id, "planned_qty": 10, "location_id": seed_data["locations"][0].id}
                ],
            },
        )

        db_session.refresh(inv_before)
        assert inv_before.available_qty == avail_before - 10
        assert inv_before.reserved_qty == reserved_before + 10


class TestPicklistQuery:
    def test_get_picklist_detail(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "DETAIL-TEST", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.get("/api/picklists/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["order_no"] == "DETAIL-TEST"

    def test_get_picklist_not_found(self, client):
        resp = client.get("/api/picklists/99999")
        assert resp.status_code == 404

    def test_list_picklists_default(self, client, seed_data):
        p1 = seed_data["products"][0].id
        for i in range(3):
            client.post(
                "/api/picklists",
                json={
                    "order_no": f"LIST-{i}",
                    "items": [{"product_id": p1, "planned_qty": 1}],
                },
            )
        resp = client.get("/api/picklists")
        body = resp.json()
        assert body["data"]["total"] == 3

    def test_list_picklists_filter_status(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "FILTER", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.get("/api/picklists?status=pending")
        assert resp.json()["data"]["total"] == 1
        resp2 = client.get("/api/picklists?status=completed")
        assert resp2.json()["data"]["total"] == 0

    def test_list_picklists_keyword(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "KEYWORD-123", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.get("/api/picklists?keyword=KEYWORD-123")
        assert resp.json()["data"]["total"] == 1


class TestPicklistUpdate:
    def test_update_picklist_success(self, client, seed_data):
        p1 = seed_data["products"][0].id
        client.post(
            "/api/picklists",
            json={"order_no": "UPDATE-TEST", "items": [{"product_id": p1, "planned_qty": 1}]},
        )
        resp = client.put(
            "/api/picklists/1",
            json={"remark": "修改备注", "priority": 10, "picker": "tester01"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remark"] == "修改备注"
        assert data["priority"] == 10
        assert data["picker"] == "tester01"

    def test_update_picklist_not_found(self, client):
        resp = client.put("/api/picklists/99999", json={"remark": "x"})
        assert resp.status_code == 404
