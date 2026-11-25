# Online Shopping — Product Catalogue & Taxonomy Engine

A full-stack **React + FastAPI + PostgreSQL (Supabase)** catalog administration platform featuring normalized multi-table schema design, hierarchical category taxonomy, universal Kaggle/CSV smart ingestion, real-time AI recommendation eligibility flagging, and automatic cloud-to-localhost failover.

## Live Deployments

- **Live Web App (Vercel):** https://product-catalogue-system-module02.vercel.app/
- **Interactive API & Swagger Docs (Render):** https://online-shopping-catalog-api.onrender.com/docs
- **Base REST API Endpoint:** `https://online-shopping-catalog-api.onrender.com/api/v1`

---

## Live Architecture & Tech Stack

| Layer              | Technology                                  | Hosting / Runtime                                           |
| :----------------- | :------------------------------------------ | :---------------------------------------------------------- |
| **Frontend UI**    | React 19, Vite, Axios, Lucide Icons         | **Vercel** (`product-catalogue-system-module02.vercel.app`) |
| **Backend API**    | Python 3.11, FastAPI, Pydantic v2, Uvicorn  | **Render** (`online-shopping-catalog-api.onrender.com`)     |
| **Relational DB**  | PostgreSQL 15+ (`psycopg` v3 binary driver) | **Supabase** (Transaction Pooler, Port `6543`)              |
| **Local Failover** | Automatic health-probe routing              | Localhost FastAPI (`:8000`) + Local PostgreSQL              |

---

## Key Capabilities

1. **Product Lifecycle & Dynamic Key-Value Attributes**
   - Full CRUD operations (`POST`, `GET`, `PATCH`, `DELETE`) with SKU uniqueness enforcement and safe fallback product thumbnails.
   - Normalized `product_attributes` storage supporting arbitrary metadata (`color`, `rating`, `battery`, `material`, `discount_percentage`) without schema migrations.
   - Inline one-click stock cycling (`IN_STOCK` → `LOW_STOCK` → `OUT_OF_STOCK`) and store visibility toggles (`ACTIVE` / `INACTIVE`).

2. **Hierarchical Category Taxonomy**
   - Multi-level parent → child category tree (`Electronics › Audio › Wireless Headphones`) with automatic URL slug generation and live SKU counts per category.

3. **Universal Kaggle & Template CSV Bulk Importer**
   - **Auto-Header Detection:** Ingests both strict catalog templates (`external_id,title,category,brand,price,stock_status`) and raw Kaggle e-commerce CSV exports (`asin`, `product_name`, `discount_price`, `main_category`, `rating`).
   - **Data Normalization & Batch Performance:** Strips currency symbols (`$`, `₹`, `€`, `£`), splits multi-level category paths, extracts extra attribute columns, and batch-inserts up to 5,000 rows in single-digit queries using `executemany`.
   - **Row-Level Validation & Audit Trail:** Logs every upload into `catalog_import_jobs` with granular row-level error reporting (duplicate SKUs, invalid prices, missing titles) without rolling back valid rows.

4. **AI Recommendation Eligibility Engine**
   - Dynamically computes `is_recommendable` (`status == 'ACTIVE'` and `stock_status IN ('IN_STOCK', 'LOW_STOCK')`) and exposes a dedicated filtered endpoint (`GET /api/v1/products?recommendable_only=true`) for downstream recommendation services.

5. **Dual-Environment Cloud-to-Localhost Failover**
   - On startup, the React client probes `https://online-shopping-catalog-api.onrender.com/api/v1/health`. If the cloud service is unreachable or offline, it seamlessly falls back to `http://127.0.0.1:8000/api/v1` and updates the sidebar connection indicator (`Cloud API + Supabase` vs. `FastAPI Connected`).

---

## Normalized PostgreSQL Schema (5 Tables)

```text
categories (id PK, parent_id FK -> categories.id, name, slug UNIQUE, is_active, created_at)
    │
    └──< products (id PK, external_id UNIQUE, title, description, category_id FK, brand,
                   price, currency, stock_status, status, image_url, created_at, updated_at)
            │
            ├──< product_attributes (id PK, product_id FK ON DELETE CASCADE, attribute_key, attribute_value)
            └──< product_categories (product_id FK, category_id FK)

catalog_import_jobs (id PK, filename, status, total_rows, valid_rows, error_rows, errors_json JSONB, created_at)
```

---

## REST API Reference

**Production Base URL:** `https://online-shopping-catalog-api.onrender.com/api/v1`  
**Interactive Swagger UI:** https://online-shopping-catalog-api.onrender.com/docs

| Method   | Endpoint                     | Auth            | Description                                                                                                                    |
| :------- | :--------------------------- | :-------------- | :----------------------------------------------------------------------------------------------------------------------------- |
| `GET`    | `/health`                    | Public          | Service health & version metadata                                                                                              |
| `GET`    | `/products`                  | Public          | Paginated search & filter (`q`, `category`, `brand`, `stock_status`, `status`, `recommendable_only`, `min_price`, `max_price`) |
| `GET`    | `/products/{id}`             | Public          | Fetch single product by UUID or SKU (`external_id`)                                                                            |
| `POST`   | `/admin/products`            | `X-Admin-Token` | Create product with dynamic attributes                                                                                         |
| `PATCH`  | `/admin/products/{id}`       | `X-Admin-Token` | Partial update (price, stock, status, attributes)                                                                              |
| `DELETE` | `/admin/products/{id}`       | `X-Admin-Token` | Delete product and cascade attributes                                                                                          |
| `POST`   | `/admin/catalog/import`      | `X-Admin-Token` | Multipart `.csv` upload with auto-mapping & audit report                                                                       |
| `GET`    | `/admin/catalog/import-jobs` | Public          | List recent CSV ingestion jobs and row validation errors                                                                       |
| `GET`    | `/categories`                | Public          | List categories with parent references and SKU counts                                                                          |
| `POST`   | `/categories`                | `X-Admin-Token` | Create top-level or child category node                                                                                        |
| `DELETE` | `/admin/reset`               | `X-Admin-Token` | Clear all catalog, category, and audit job records                                                                             |

---

## Project Structure

```text
prototype/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI routes, batch CSV ingestion, eligibility logic
│   │   ├── database.py        # PostgreSQL connection pool & schema auto-initialization
│   │   ├── schemas.py         # Pydantic v2 request/response validation models
│   │   └── csv_mapper.py      # Heuristic Kaggle/CSV column mapper & row sanitizer
│   ├── tests/
│   │   └── test_catalog.py    # Automated Pytest integration suite
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── er_diagram.png     # Schema diagram rendered in the ER Diagram tab
│   ├── src/
│   │   ├── components/
│   │   │   └── ProductModal.jsx
│   │   ├── services/
│   │   │   └── api.js         # Cloud-to-localhost failover & cache-busted Axios client
│   │   ├── App.jsx            # Catalog Admin dashboard (Products, Categories, Bulk Import, ERD)
│   │   ├── App.css            # Navy & Teal enterprise design system + skeleton loaders
│   │   └── main.jsx
│   └── .env.example
├── .gitignore
└── README.md
```

---

## Local Development Setup

### 1. Backend (FastAPI + PostgreSQL)

```bash
cd backend
cp .env.example .env
# Edit .env and set DATABASE_URL (Supabase URI or local PostgreSQL URI)
py -m pip install -r requirements.txt
py -m pytest
py -m uvicorn app.main:app --reload
```

Local API & Swagger UI run at `http://127.0.0.1:8000/docs`.

### 2. Frontend (React + Vite)

```bash
cd frontend
cp .env.example .env.local
# Leave VITE_API_BASE_URL blank for localhost mode
npm.cmd install
npm.cmd run dev
```

Local Admin Dashboard runs at `http://localhost:5173`.

---

## Cloud Deployment & Demo Notes (Render + Vercel)

1. **Backend (Render Web Service — `https://online-shopping-catalog-api.onrender.com`):**
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables:** `DATABASE_URL` (Supabase pooler URI), `ADMIN_API_KEY`, `PYTHON_VERSION=3.11.9`
2. **Frontend (Vercel — `https://product-catalogue-system-module02.vercel.app/`):**
   - **Root Directory:** `frontend`
   - **Environment Variables:** `VITE_API_BASE_URL=https://online-shopping-catalog-api.onrender.com/api/v1`, `VITE_ADMIN_TOKEN`
3. **ER Diagram Asset:**
   - Place `er_diagram.png` inside `frontend/public/er_diagram.png` so the **ER Diagram** tab renders automatically on both local and hosted builds.
4. **Render Free-Tier Cold Start:**
   - Render free instances sleep after 15 minutes of inactivity (~30s wake-up on the first request). Open https://product-catalogue-system-module02.vercel.app/ ~1 minute prior to a live demo so the backend is warm.
