import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

from app.csv_mapper import detect_column_mapping, parse_row_with_mapping
from app.database import get_db, init_db
from app.schemas import ALLOWED_STATUS, ALLOWED_STOCK, CategoryCreate, ProductCreate, ProductUpdate

load_dotenv()

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-catalog-admin-token")
MAX_CSV_IMPORT_ROWS = int(os.getenv("MAX_CSV_IMPORT_ROWS", "1000"))
CLOUD_DATABASE_URL = os.getenv("CLOUD_DATABASE_URL", "").strip()

app = FastAPI(
    title="Product Catalogue & Taxonomy API",
    description="Normalized PostgreSQL product catalogue, hierarchical category taxonomy, smart Kaggle CSV ingestion, and AI recommendation eligibility service.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def compute_eligibility(status: str, stock_status: str) -> bool:
    return status == "ACTIVE" and stock_status in {"IN_STOCK", "LOW_STOCK"}


def mirror_local_to_cloud():
    """Mirrors local PostgreSQL state to Supabase whenever CLOUD_DATABASE_URL is configured."""
    if not CLOUD_DATABASE_URL:
        return
    try:
        with get_db() as l_conn:
            with l_conn.cursor() as l_cur:
                l_cur.execute("SELECT * FROM categories ORDER BY created_at ASC")
                cats = l_cur.fetchall()
                l_cur.execute("SELECT * FROM products ORDER BY created_at ASC")
                prods = l_cur.fetchall()
                l_cur.execute("SELECT * FROM product_attributes")
                attrs = l_cur.fetchall()
                l_cur.execute("SELECT * FROM catalog_import_jobs ORDER BY created_at ASC")
                jobs = l_cur.fetchall()

        with psycopg.connect(CLOUD_DATABASE_URL, row_factory=dict_row) as c_conn:
            with c_conn.cursor() as c_cur:
                c_cur.execute("DELETE FROM product_attributes;")
                c_cur.execute("DELETE FROM product_categories;")
                c_cur.execute("DELETE FROM products;")
                c_cur.execute("DELETE FROM categories;")
                c_cur.execute("DELETE FROM catalog_import_jobs;")

                if cats:
                    c_cur.executemany(
                        "INSERT INTO categories (id, parent_id, name, slug, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                        [(c["id"], c["parent_id"], c["name"], c["slug"], c["is_active"], c["created_at"]) for c in cats],
                    )
                if prods:
                    c_cur.executemany(
                        """
                        INSERT INTO products (id, external_id, title, description, category_id, brand, price, currency, stock_status, status, image_url, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            (
                                p["id"], p["external_id"], p["title"], p["description"], p["category_id"],
                                p["brand"], p["price"], p["currency"], p["stock_status"], p["status"],
                                p["image_url"], p["created_at"], p["updated_at"],
                            )
                            for p in prods
                        ],
                    )
                if attrs:
                    c_cur.executemany(
                        "INSERT INTO product_attributes (id, product_id, attribute_key, attribute_value) VALUES (%s, %s, %s, %s)",
                        [(a["id"], a["product_id"], a["attribute_key"], a["attribute_value"]) for a in attrs],
                    )
                if jobs:
                    c_cur.executemany(
                        """
                        INSERT INTO catalog_import_jobs (id, filename, status, total_rows, valid_rows, error_rows, errors_json, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        """,
                        [
                            (
                                j["id"], j["filename"], j["status"], j["total_rows"],
                                j["valid_rows"], j["error_rows"], json.dumps(j["errors_json"]), j["created_at"],
                            )
                            for j in jobs
                        ],
                    )
            c_conn.commit()
    except Exception as exc:
        print(f"[Dual-Sync Warning] Could not mirror to Supabase: {exc}")


def get_or_create_category(cur, category_name: str) -> str:
    slug = category_name.strip().lower().replace(" ", "-").replace("'", "")
    cur.execute(
        "SELECT id FROM categories WHERE slug = %s OR LOWER(name) = LOWER(%s)",
        (slug, category_name.strip()),
    )
    row = cur.fetchone()
    if row:
        return str(row["id"])
    cur.execute(
        "INSERT INTO categories (parent_id, name, slug, is_active) VALUES (NULL, %s, %s, TRUE) RETURNING id",
        (category_name.strip(), slug),
    )
    return str(cur.fetchone()["id"])


def serialize_product(cur, row: Dict[str, Any]) -> Dict[str, Any]:
    cur.execute("SELECT id, name, slug FROM categories WHERE id = %s", (row["category_id"],))
    cat = cur.fetchone()
    cur.execute(
        "SELECT attribute_key, attribute_value FROM product_attributes WHERE product_id = %s",
        (row["id"],),
    )
    attrs = cur.fetchall()
    return {
        "id": str(row["id"]),
        "external_id": row["external_id"],
        "title": row["title"],
        "description": row["description"],
        "category": {"id": str(cat["id"]), "name": cat["name"], "slug": cat["slug"]} if cat else None,
        "brand": row["brand"],
        "price": float(row["price"]),
        "currency": row["currency"],
        "stock_status": row["stock_status"],
        "status": row["status"],
        "is_recommendable": compute_eligibility(row["status"], row["stock_status"]),
        "image_url": row["image_url"],
        "attributes": {a["attribute_key"]: a["attribute_value"] for a in attrs},
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def verify_admin(x_admin_token: Optional[str]):
    if x_admin_token is not None and x_admin_token != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized: catalog_admin role required")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Product Catalogue & Taxonomy API",
        "version": "2.0.0",
        "dual_sync": bool(CLOUD_DATABASE_URL),
        "docs": "/docs",
    }


@app.get("/api/v1/products")
def list_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    stock_status: Optional[str] = None,
    status: Optional[str] = None,
    recommendable_only: bool = False,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    query = """
        SELECT p.* FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    """
    params: List[Any] = []

    if q:
        query += " AND (LOWER(p.title) LIKE %s OR LOWER(p.external_id) LIKE %s OR LOWER(p.brand) LIKE %s)"
        like_q = f"%{q.lower()}%"
        params.extend([like_q, like_q, like_q])
    if category:
        query += " AND (LOWER(c.name) = LOWER(%s) OR LOWER(c.slug) = LOWER(%s))"
        params.extend([category, category])
    if brand:
        query += " AND LOWER(p.brand) = LOWER(%s)"
        params.append(brand)
    if stock_status:
        query += " AND p.stock_status = %s"
        params.append(stock_status.upper())
    if status:
        query += " AND p.status = %s"
        params.append(status.upper())
    if recommendable_only:
        query += " AND p.status = 'ACTIVE' AND p.stock_status IN ('IN_STOCK', 'LOW_STOCK')"
    if min_price is not None:
        query += " AND p.price >= %s"
        params.append(min_price)
    if max_price is not None:
        query += " AND p.price <= %s"
        params.append(max_price)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM ({query}) sub", params)
            total = cur.fetchone()["cnt"]

            query += " ORDER BY p.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, (page - 1) * limit])
            cur.execute(query, params)
            rows = cur.fetchall()
            items = [serialize_product(cur, r) for r in rows]

    return {"page": page, "limit": limit, "total": total, "items": items}


@app.get("/api/v1/products/{product_id}")
def get_product(product_id: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM products WHERE id::text = %s OR LOWER(external_id) = LOWER(%s)",
                (product_id, product_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Product not found")
            return serialize_product(cur, row)


@app.post("/api/v1/admin/products", status_code=201)
def create_product(
    payload: ProductCreate,
    background_tasks: BackgroundTasks,
    x_admin_token: Optional[str] = Header(default=None),
):
    verify_admin(x_admin_token)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM products WHERE LOWER(external_id) = LOWER(%s)",
                (payload.external_id,),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate external_id '{payload.external_id}' already exists",
                )

            cat_id = get_or_create_category(cur, payload.category)
            cur.execute(
                """
                INSERT INTO products (external_id, title, description, category_id, brand, price, currency, stock_status, status, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.external_id,
                    payload.title,
                    payload.description,
                    cat_id,
                    payload.brand,
                    payload.price,
                    payload.currency.upper(),
                    payload.stock_status,
                    payload.status,
                    payload.image_url,
                ),
            )
            created = cur.fetchone()

            if payload.attributes:
                for k, v in payload.attributes.items():
                    cur.execute(
                        "INSERT INTO product_attributes (product_id, attribute_key, attribute_value) VALUES (%s, %s, %s)",
                        (created["id"], k.strip(), str(v).strip()),
                    )

            result = serialize_product(cur, created)
        conn.commit()
    background_tasks.add_task(mirror_local_to_cloud)
    return result


@app.patch("/api/v1/admin/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductUpdate,
    background_tasks: BackgroundTasks,
    x_admin_token: Optional[str] = Header(default=None),
):
    verify_admin(x_admin_token)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM products WHERE id::text = %s OR LOWER(external_id) = LOWER(%s)",
                (product_id, product_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Product not found")

            updates = []
            params = []
            if payload.title is not None:
                updates.append("title = %s")
                params.append(payload.title.strip())
            if payload.description is not None:
                updates.append("description = %s")
                params.append(payload.description)
            if payload.category is not None:
                cat_id = get_or_create_category(cur, payload.category)
                updates.append("category_id = %s")
                params.append(cat_id)
            if payload.brand is not None:
                updates.append("brand = %s")
                params.append(payload.brand.strip())
            if payload.price is not None:
                updates.append("price = %s")
                params.append(payload.price)
            if payload.stock_status is not None:
                stk = payload.stock_status.upper()
                if stk not in ALLOWED_STOCK:
                    raise HTTPException(status_code=422, detail="Invalid stock_status")
                updates.append("stock_status = %s")
                params.append(stk)
            if payload.status is not None:
                sts = payload.status.upper()
                if sts not in ALLOWED_STATUS:
                    raise HTTPException(status_code=422, detail="Invalid status")
                updates.append("status = %s")
                params.append(sts)
            if payload.image_url is not None:
                updates.append("image_url = %s")
                params.append(payload.image_url)

            if updates:
                updates.append("updated_at = %s")
                params.append(datetime.now(timezone.utc))
                params.append(row["id"])
                cur.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = %s RETURNING *", params)
                row = cur.fetchone()

            if payload.attributes is not None:
                cur.execute("DELETE FROM product_attributes WHERE product_id = %s", (row["id"],))
                for k, v in payload.attributes.items():
                    cur.execute(
                        "INSERT INTO product_attributes (product_id, attribute_key, attribute_value) VALUES (%s, %s, %s)",
                        (row["id"], k.strip(), str(v).strip()),
                    )

            result = serialize_product(cur, row)
        conn.commit()
    background_tasks.add_task(mirror_local_to_cloud)
    return result


@app.delete("/api/v1/admin/products/{product_id}")
def delete_product(
    product_id: str,
    background_tasks: BackgroundTasks,
    x_admin_token: Optional[str] = Header(default=None),
):
    verify_admin(x_admin_token)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM products WHERE id::text = %s OR LOWER(external_id) = LOWER(%s) RETURNING external_id",
                (product_id, product_id),
            )
            deleted = cur.fetchone()
            if not deleted:
                raise HTTPException(status_code=404, detail="Product not found")
        conn.commit()
    background_tasks.add_task(mirror_local_to_cloud)
    return {"deleted": True, "external_id": deleted["external_id"]}


@app.post("/api/v1/admin/catalog/import")
async def import_catalog_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_rows: int = Query(default=MAX_CSV_IMPORT_ROWS, ge=1, le=5000),
    x_admin_token: Optional[str] = Header(default=None),
):
    verify_admin(x_admin_token)
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    all_rows = list(reader)

    mapping = detect_column_mapping(headers, all_rows[:20])
    is_strict_template = "external_id" in [h.lower().strip() for h in headers if h]

    total_rows = 0
    valid_items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT LOWER(external_id) AS sku FROM products")
            existing_skus = {r["sku"] for r in cur.fetchall()}

            cur.execute("SELECT id, slug, LOWER(name) AS lname FROM categories")
            cat_cache: Dict[str, str] = {}
            for r in cur.fetchall():
                cat_cache[r["slug"]] = str(r["id"])
                cat_cache[r["lname"]] = str(r["id"])

            for idx, row in enumerate(all_rows[:max_rows], start=2):
                total_rows += 1
                parsed, err_msg = parse_row_with_mapping(row, idx, mapping, is_strict_template)

                if err_msg or not parsed:
                    raw_id = (row.get(mapping.get("external_id") or "") or "MISSING").strip()
                    errors.append({"row": idx, "external_id": raw_id, "issue": err_msg or "Invalid row"})
                    continue

                sku_low = parsed["external_id"].lower()
                if sku_low in existing_skus:
                    errors.append({
                        "row": idx,
                        "external_id": parsed["external_id"],
                        "issue": f"Duplicate SKU '{parsed['external_id']}' already exists",
                    })
                    continue

                existing_skus.add(sku_low)
                valid_items.append(parsed)

            for item in valid_items:
                cat_name = item["category"]
                slug = cat_name.strip().lower().replace(" ", "-").replace("'", "")
                if slug not in cat_cache and cat_name.lower() not in cat_cache:
                    cur.execute(
                        "INSERT INTO categories (parent_id, name, slug, is_active) VALUES (NULL, %s, %s, TRUE) RETURNING id",
                        (cat_name.strip(), slug),
                    )
                    new_id = str(cur.fetchone()["id"])
                    cat_cache[slug] = new_id
                    cat_cache[cat_name.lower()] = new_id
                item["category_id"] = cat_cache.get(slug) or cat_cache[cat_name.lower()]

            if valid_items:
                product_params = [
                    (
                        it["external_id"],
                        it["title"],
                        it["description"],
                        it["category_id"],
                        it["brand"],
                        it["price"],
                        it["stock_status"],
                        it["image_url"],
                    )
                    for it in valid_items
                ]
                cur.executemany(
                    """
                    INSERT INTO products (external_id, title, description, category_id, brand, price, currency, stock_status, status, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s, 'USD', %s, 'ACTIVE', %s)
                    """,
                    product_params,
                )

                inserted_skus = [it["external_id"] for it in valid_items if it["attributes"]]
                if inserted_skus:
                    cur.execute(
                        "SELECT id, external_id FROM products WHERE external_id = ANY(%s)",
                        (inserted_skus,),
                    )
                    id_map = {r["external_id"]: r["id"] for r in cur.fetchall()}
                    attr_params = []
                    for it in valid_items:
                        pid = id_map.get(it["external_id"])
                        if pid and it["attributes"]:
                            for ak, av in it["attributes"].items():
                                attr_params.append((pid, ak, av))
                    if attr_params:
                        cur.executemany(
                            "INSERT INTO product_attributes (product_id, attribute_key, attribute_value) VALUES (%s, %s, %s)",
                            attr_params,
                        )

            valid_rows = len(valid_items)
            error_rows = len(errors)
            job_status = "COMPLETED_WITH_ERRORS" if error_rows > 0 else "COMPLETED"

            cur.execute(
                """
                INSERT INTO catalog_import_jobs (filename, status, total_rows, valid_rows, error_rows, errors_json)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (file.filename, job_status, total_rows, valid_rows, error_rows, json.dumps(errors[:100])),
            )
            job_id = str(cur.fetchone()["id"])
        conn.commit()

    background_tasks.add_task(mirror_local_to_cloud)
    return {
        "job_id": job_id,
        "filename": file.filename,
        "detected_mapping": mapping,
        "status": job_status,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "error_rows": error_rows,
        "errors": errors[:100],
    }


@app.get("/api/v1/admin/catalog/import-jobs")
def list_import_jobs():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM catalog_import_jobs ORDER BY created_at DESC LIMIT 20")
            rows = cur.fetchall()
            return {
                "jobs": [
                    {
                        "job_id": str(r["id"]),
                        "filename": r["filename"],
                        "status": r["status"],
                        "total_rows": r["total_rows"],
                        "valid_rows": r["valid_rows"],
                        "error_rows": r["error_rows"],
                        "errors": r["errors_json"],
                        "created_at": r["created_at"].isoformat(),
                    }
                    for r in rows
                ]
            }


@app.get("/api/v1/admin/catalog/import-jobs/{job_id}")
def get_import_job(job_id: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM catalog_import_jobs WHERE id::text = %s", (job_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Import job not found")
            return {
                "job_id": str(row["id"]),
                "filename": row["filename"],
                "status": row["status"],
                "total_rows": row["total_rows"],
                "valid_rows": row["valid_rows"],
                "error_rows": row["error_rows"],
                "errors": row["errors_json"],
                "created_at": row["created_at"].isoformat(),
            }


@app.get("/api/v1/categories")
def list_categories():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.*, COUNT(p.id) AS product_count
                FROM categories c
                LEFT JOIN products p ON p.category_id = c.id
                GROUP BY c.id
                ORDER BY c.name ASC
            """)
            rows = cur.fetchall()
            return {
                "categories": [
                    {
                        "id": str(r["id"]),
                        "parent_id": str(r["parent_id"]) if r["parent_id"] else None,
                        "name": r["name"],
                        "slug": r["slug"],
                        "is_active": r["is_active"],
                        "product_count": r["product_count"],
                    }
                    for r in rows
                ]
            }


@app.post("/api/v1/categories", status_code=201)
def create_category(
    payload: CategoryCreate,
    background_tasks: BackgroundTasks,
    x_admin_token: Optional[str] = Header(default=None),
):
    verify_admin(x_admin_token)
    slug = payload.slug.strip().lower().replace(" ", "-")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM categories WHERE slug = %s", (slug,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=f"Category slug '{slug}' already exists")
            cur.execute(
                "INSERT INTO categories (parent_id, name, slug, is_active) VALUES (%s, %s, %s, TRUE) RETURNING id",
                (payload.parent_id or None, payload.name.strip(), slug),
            )
            cat_id = str(cur.fetchone()["id"])
        conn.commit()
    background_tasks.add_task(mirror_local_to_cloud)
    return {
        "id": cat_id,
        "parent_id": payload.parent_id or None,
        "name": payload.name.strip(),
        "slug": slug,
        "is_active": True,
        "product_count": 0,
    }


@app.delete("/api/v1/admin/reset")
def reset_all_data(
    background_tasks: BackgroundTasks,
    x_admin_token: Optional[str] = Header(default=None),
):
    verify_admin(x_admin_token)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM product_attributes;")
            cur.execute("DELETE FROM product_categories;")
            cur.execute("DELETE FROM products;")
            cur.execute("DELETE FROM categories;")
            cur.execute("DELETE FROM catalog_import_jobs;")
        conn.commit()
    background_tasks.add_task(mirror_local_to_cloud)
    return {"message": "All PostgreSQL catalog tables cleared"}


@app.post("/api/v1/admin/sync-cloud-to-local")
def sync_cloud_to_local(x_admin_token: Optional[str] = Header(default=None)):
    verify_admin(x_admin_token)
    if not CLOUD_DATABASE_URL:
        raise HTTPException(
            status_code=400,
            detail="CLOUD_DATABASE_URL is not configured in local backend/.env",
        )

    with psycopg.connect(CLOUD_DATABASE_URL, row_factory=dict_row) as cloud_conn:
        with cloud_conn.cursor() as c_cur:
            c_cur.execute("SELECT * FROM categories ORDER BY created_at ASC")
            cloud_cats = c_cur.fetchall()
            c_cur.execute("SELECT * FROM products ORDER BY created_at ASC")
            cloud_prods = c_cur.fetchall()
            c_cur.execute("SELECT * FROM product_attributes")
            cloud_attrs = c_cur.fetchall()
            c_cur.execute("SELECT * FROM catalog_import_jobs ORDER BY created_at ASC")
            cloud_jobs = c_cur.fetchall()

    with get_db() as local_conn:
        with local_conn.cursor() as l_cur:
            l_cur.execute("DELETE FROM product_attributes;")
            l_cur.execute("DELETE FROM product_categories;")
            l_cur.execute("DELETE FROM products;")
            l_cur.execute("DELETE FROM categories;")
            l_cur.execute("DELETE FROM catalog_import_jobs;")

            if cloud_cats:
                l_cur.executemany(
                    "INSERT INTO categories (id, parent_id, name, slug, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    [(c["id"], c["parent_id"], c["name"], c["slug"], c["is_active"], c["created_at"]) for c in cloud_cats],
                )
            if cloud_prods:
                l_cur.executemany(
                    """
                    INSERT INTO products (id, external_id, title, description, category_id, brand, price, currency, stock_status, status, image_url, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            p["id"], p["external_id"], p["title"], p["description"], p["category_id"],
                            p["brand"], p["price"], p["currency"], p["stock_status"], p["status"],
                            p["image_url"], p["created_at"], p["updated_at"],
                        )
                        for p in cloud_prods
                    ],
                )
            if cloud_attrs:
                l_cur.executemany(
                    "INSERT INTO product_attributes (id, product_id, attribute_key, attribute_value) VALUES (%s, %s, %s, %s)",
                    [(a["id"], a["product_id"], a["attribute_key"], a["attribute_value"]) for a in cloud_attrs],
                )
            if cloud_jobs:
                l_cur.executemany(
                    """
                    INSERT INTO catalog_import_jobs (id, filename, status, total_rows, valid_rows, error_rows, errors_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    [
                        (
                            j["id"], j["filename"], j["status"], j["total_rows"],
                            j["valid_rows"], j["error_rows"], json.dumps(j["errors_json"]), j["created_at"],
                        )
                        for j in cloud_jobs
                    ],
                )
        local_conn.commit()

    return {
        "synced": True,
        "categories": len(cloud_cats),
        "products": len(cloud_prods),
        "attributes": len(cloud_attrs),
        "import_jobs": len(cloud_jobs),
    }