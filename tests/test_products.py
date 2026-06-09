from app import crud, schemas
from app.models import ProductStatus


class TestProductCreate:
    def test_create_product_success(self, client):
        payload = {
            "sku": "NEWSKU001",
            "name": "新建商品1",
            "category": "测试",
            "specification": "spec",
            "unit": "件",
            "weight": 1.0,
            "barcode": "1234567890123",
        }
        resp = client.post("/api/products", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sku"] == "NEWSKU001"
        assert data["name"] == "新建商品1"
        assert data["id"] is not None
        assert data["status"] == "active"

    def test_create_product_duplicate_sku(self, client, seed_data):
        payload = {
            "sku": "SKU001",
            "name": "重复SKU",
            "category": "测试",
            "specification": "spec",
            "unit": "件",
        }
        resp = client.post("/api/products", json=payload)
        assert resp.status_code == 400
        assert "已存在" in resp.json()["detail"]

    def test_create_product_missing_required_fields(self, client):
        payload = {"name": "缺SKU商品"}
        resp = client.post("/api/products", json=payload)
        assert resp.status_code == 422


class TestProductQuery:
    def test_get_product_by_id(self, client, seed_data):
        pid = seed_data["products"][0].id
        resp = client.get(f"/api/products/{pid}")
        assert resp.status_code == 200
        assert resp.json()["sku"] == "SKU001"

    def test_get_product_not_found(self, client):
        resp = client.get("/api/products/99999")
        assert resp.status_code == 404

    def test_list_products_default(self, client, seed_data):
        resp = client.get("/api/products")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["total"] == 3
        assert len(body["data"]["items"]) == 3

    def test_list_products_with_keyword(self, client, seed_data):
        resp = client.get("/api/products?keyword=SKU001")
        body = resp.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["sku"] == "SKU001"

    def test_list_products_with_status(self, client, seed_data):
        resp = client.get("/api/products?status=active")
        body = resp.json()
        assert body["data"]["total"] == 3

    def test_list_products_pagination(self, client, seed_data):
        resp = client.get("/api/products?page=1&page_size=2")
        body = resp.json()
        assert len(body["data"]["items"]) == 2
        assert body["data"]["pages"] == 2


class TestProductUpdate:
    def test_update_product_success(self, client, seed_data):
        pid = seed_data["products"][0].id
        resp = client.put(
            f"/api/products/{pid}",
            json={"name": "修改后商品名", "weight": 9.9},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "修改后商品名"
        assert data["weight"] == 9.9

    def test_update_product_not_found(self, client):
        resp = client.put(
            "/api/products/99999",
            json={"name": "不存在的商品"},
        )
        assert resp.status_code == 404

    def test_update_product_invalid_status(self, client, seed_data):
        pid = seed_data["products"][0].id
        resp = client.put(
            f"/api/products/{pid}",
            json={"status": "invalid_status_xxx"},
        )
        assert resp.status_code == 422
