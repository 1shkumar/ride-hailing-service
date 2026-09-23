from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_full_booking_flow_via_http():
    user = client.post("/users", json={"name": "Alice", "phone": "111"}).json()
    client.post(
        "/drivers",
        json={"name": "Bob", "phone": "222", "car_type": "SEDAN", "lat": 12.9716, "lon": 77.5946},
    )

    booked = client.post(
        "/rides/book",
        json={
            "user_id": user["id"],
            "pickup_lat": 12.9716,
            "pickup_lon": 77.5946,
            "car_type": "SEDAN",
            "radius_km": 5,
        },
    )
    assert booked.status_code == 200
    ride = booked.json()
    assert ride["status"] == "ONGOING"

    ended = client.post(f"/rides/{ride['id']}/end", json={"drop_lat": 13.0, "drop_lon": 77.6})
    assert ended.status_code == 200
    assert ended.json()["status"] == "COMPLETED"
    assert ended.json()["final_fare"] > 0


def test_no_driver_in_radius_returns_409():
    user = client.post("/users", json={"name": "Carol", "phone": "333"}).json()
    resp = client.post(
        "/rides/book",
        json={"user_id": user["id"], "pickup_lat": 50.0, "pickup_lon": 50.0, "car_type": "SEDAN", "radius_km": 1},
    )
    assert resp.status_code == 409


def test_unknown_user_returns_404():
    resp = client.post(
        "/rides/book",
        json={"user_id": "ghost", "pickup_lat": 0, "pickup_lon": 0, "car_type": "SEDAN", "radius_km": 5},
    )
    assert resp.status_code == 404


def test_coupon_lifecycle_via_http():
    add = client.post("/coupons", json={"code": "API10", "discount_type": "FLAT", "value": 10})
    assert add.status_code == 200
    assert add.json()["code"] == "API10"

    delete = client.delete("/coupons/API10")
    assert delete.status_code == 200

    delete_again = client.delete("/coupons/API10")
    assert delete_again.status_code == 404


def test_hatchback_to_sedan_upgrade_via_http():
    user = client.post("/users", json={"name": "Dave", "phone": "444"}).json()
    client.post(
        "/drivers",
        json={"name": "OnlySedan", "phone": "555", "car_type": "SEDAN", "lat": 19.0760, "lon": 72.8777},
    )
    booked = client.post(
        "/rides/book",
        json={
            "user_id": user["id"],
            "pickup_lat": 19.0760,
            "pickup_lon": 72.8777,
            "car_type": "HATCHBACK",
            "radius_km": 5,
        },
    )
    assert booked.status_code == 200
    ride = booked.json()
    assert ride["car_type_requested"] == "HATCHBACK"
    assert ride["car_type_assigned"] == "SEDAN"
