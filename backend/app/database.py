import os
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Lisajith%40123@localhost:5432/online_shopping_db",
)


def get_db():
    # prepare_threshold=None prevents PgBouncer/Supabase pooler prepared-statement errors
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        prepare_threshold=None,
    )


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

            cur.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    parent_id UUID NULL REFERENCES categories(id) ON DELETE SET NULL,
                    name VARCHAR(100) NOT NULL,
                    slug VARCHAR(120) NOT NULL UNIQUE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    external_id VARCHAR(64) NOT NULL UNIQUE,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
                    brand VARCHAR(100) NOT NULL,
                    price NUMERIC(10, 2) NOT NULL CHECK (price > 0),
                    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    stock_status VARCHAR(20) NOT NULL DEFAULT 'IN_STOCK',
                    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                    image_url VARCHAR(500),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS product_categories (
                    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                    PRIMARY KEY (product_id, category_id)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS product_attributes (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    attribute_key VARCHAR(64) NOT NULL,
                    attribute_value VARCHAR(255) NOT NULL
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS catalog_import_jobs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    uploaded_by UUID NULL,
                    filename VARCHAR(255) NOT NULL,
                    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
                    total_rows INTEGER NOT NULL DEFAULT 0,
                    valid_rows INTEGER NOT NULL DEFAULT 0,
                    error_rows INTEGER NOT NULL DEFAULT 0,
                    errors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
        conn.commit()