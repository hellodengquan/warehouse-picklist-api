class TestLocationCreate:
    def test_create_location_success(self, client):
        payload = {
            "code": "C-03-02-01",
            "zone": "C区",
            "aisle": "03",
            "shelf": "02",
            "level": "01",
            "position": "01",
            "capacity": 5,
        }
        resp = client.post("/api/locations", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "C-03-02-01"
        assert data["zone"] == "C区"
        assert data["status"] == "available"

    def test_create_location_duplicate_code(self, client, seed_data):
        payload = {
            "code": "A-01-01-01",
            "zone": "X区",
        }
        resp = client.post("/api/locations", json=payload)
        assert resp.status_code == 400
        assert "已存在" in resp.json()["detail"]

    def test_create_location_missing_required(self, client):
        payload = {"zone": "缺code"}
        resp = client.post("/api/locations", json=payload)
        assert resp.status_code == 422


class TestLocationQuery:
    def test_get_location_by_id(self, client, seed_data):
        lid = seed_data["locations"][0].id
        resp = client.get(f"/api/locations/{lid}")
        assert resp.status_code == 200
        assert resp.json()["code"] == "A-01-01-01"

    def test_get_location_not_found(self, client):
        resp = client.get("/api/locations/99999")
        assert resp.status_code == 404

    def test_list_locations(self, client, seed_data):
        resp = client.get("/api/locations")
        body = resp.json()
        assert body["data"]["total"] == 3

    def test_list_locations_by_zone(self, client, seed_data):
        resp = client.get("/api/locations?zone=B区")
        body = resp.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["code"] == "B-02-03-04"

    def test_list_locations_keyword(self, client, seed_data):
        resp = client.get("/api/locations?keyword=A-01-01")
        body = resp.json()
        assert body["data"]["total"] == 2


class TestLocationUpdate:
    def test_update_location_success(self, client, seed_data):
        lid = seed_data["locations"][0].id
        resp = client.put(
            f"/api/locations/{lid}",
            json={"description": "修改描述", "capacity": 99},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "修改描述"
        assert data["capacity"] == 99

    def test_update_location_not_found(self, client):
        resp = client.put("/api/locations/99999", json={"description": "x"})
        assert resp.status_code == 404

    def test_update_location_invalid_status(self, client, seed_data):
        lid = seed_data["locations"][0].id
        resp = client.put(f"/api/locations/{lid}", json={"status": "invalid"})
        assert resp.status_code == 422
