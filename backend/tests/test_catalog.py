import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def setup_function():
    client.delete("/api/v1/admin/reset")


def test_create_edit_and_delete_product():
    res = client.post("/api/v1/admin/products", json={
        "external_id": "SKU-TEST-01",
        "title": "Sony WH-1000XM5 Headphones",
        "category": "Wireless Headphones",
        "brand": "Sony",
        "price": 299.00,
        "stock_status": "IN_STOCK",
        "attributes": {"color": "black", "battery": "30h"}
    })
    assert res.status_code == 201
    assert res.json()["is_recommendable"] is True

    patch_res = client.patch("/api/v1/admin/products/SKU-TEST-01", json={
        "price": 279.00,
        "attributes": {"color": "silver", "warranty": "2y"}
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["price"] == 279.00
    assert patch_res.json()["attributes"]["color"] == "silver"

    del_res = client.delete("/api/v1/admin/products/SKU-TEST-01")
    assert del_res.status_code == 200


def test_raw_kaggle_csv_auto_mapping():
    kaggle_csv = (
        "asin,product_name,main_category,brand,discount_price,rating\n"
        "B09X123,OnePlus Buds Pro 2,Electronics > Audio,OnePlus,\"₹7,999\",4.5\n"
        "B09X124,Logitech MX Keys,Computers | Keyboards,Logitech,$99.99,4.8\n"
    )
    files = {"file": ("kaggle_amazon_sample.csv", io.BytesIO(kaggle_csv.encode("utf-8")), "text/csv")}
    res = client.post("/api/v1/admin/catalog/import", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["valid_rows"] == 2
    assert body["error_rows"] == 0
    assert body["detected_mapping"]["title"] == "product_name"

    prod = client.get("/api/v1/products/B09X123").json()
    assert prod["category"]["name"] == "Electronics"
    assert prod["attributes"]["rating"] == "4.5"