# Module 02 — Product Catalogue & Taxonomy Engine

A full-stack **React + FastAPI + PostgreSQL (Supabase)** product catalogue, hierarchical taxonomy, smart Kaggle CSV ingestion, and AI recommendation eligibility service.

## Features

- **Full Product CRUD & Dynamic Attributes:** Create, search, filter, edit (`PATCH`), and delete (`DELETE`) products with arbitrary key-value attributes (`color`, `rating`, `ram`, `warranty`) stored in normalized PostgreSQL tables.
- **Hierarchical Category Taxonomy:** Multi-level parent → child category management with automatic slug generation and live SKU counts.
- **Universal Kaggle CSV Smart Importer:** Automatically detects and normalizes headers from standard templates or arbitrary Kaggle e-commerce CSVs (`asin`, `product_name`, `discount_price`, `main_category`), strips currency symbols (`$`/`₹`), extracts extra attributes, and logs row-level audit reports.
- **AI Recommendation Eligibility:** Real-time eligibility computation (`ACTIVE` + `IN_STOCK`/`LOW_STOCK`) with dedicated API filtering (`?recommendable_only=true`).
- **Dual-Environment Resilience:** Automatically connects to the hosted cloud API when deployed and seamlessly falls back to `localhost` during offline local demos.

## Local Setup

### 1. Backend (FastAPI + PostgreSQL)

```bash
cd backend
cp .env.example .env   # Add your PostgreSQL / Supabase DATABASE_URL
py -m pip install -r requirements.txt
py -m pytest
py -m uvicorn app.main:app --reload
```
