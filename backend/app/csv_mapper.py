import re
from typing import Any, Dict, List, Optional, Tuple

COLUMN_HINTS = {
    "external_id": ["external_id", "uniq_id", "asin", "sku", "product_id", "item_id", "id", "code"],
    "title": ["title", "product_name", "item_name", "name", "product_title"],
    "category": [
        "category",
        "main_category",
        "sub_category",
        "product_category_tree",
        "department",
        "articletype",
        "mastercategory",
    ],
    "brand": ["brand", "brand_name", "manufacturer", "vendor", "company", "seller"],
    "price": [
        "price",
        "discount_price",
        "discounted_price",
        "selling_price",
        "retail_price",
        "actual_price",
        "mrp",
        "cost",
        "amount",
    ],
    "stock_status": ["stock_status", "stock", "availability", "in_stock"],
    "image_url": ["image_url", "image", "img", "img_link", "image_link", "thumbnail", "picture"],
    "description": ["description", "about_product", "details", "summary"],
}

EXTRA_ATTRIBUTE_HINTS = {
    "rating",
    "ratings",
    "rating_count",
    "no_of_ratings",
    "discount_percentage",
    "color",
    "colour",
    "size",
    "material",
    "weight",
    "gender",
    "season",
}


def detect_column_mapping(headers: List[str], sample_rows: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    lower_map = {h.lower().strip(): h for h in headers if h}
    mapping: Dict[str, Optional[str]] = {}

    for target, hints in COLUMN_HINTS.items():
        found = None
        for hint in hints:
            if hint in lower_map:
                found = lower_map[hint]
                break
        if not found:
            for hint in hints:
                for h_low, h_orig in lower_map.items():
                    if hint in h_low and h_orig not in mapping.values():
                        found = h_orig
                        break
                if found:
                    break
        mapping[target] = found

    if not mapping["price"] and sample_rows:
        for h in headers:
            vals = [str(r.get(h, "")) for r in sample_rows[:10]]
            hits = sum(1 for v in vals if re.search(r"[$₹€£]?\s*\d+(\.\d+)?", v))
            if hits >= max(1, len(vals) // 2):
                mapping["price"] = h
                break

    return mapping


def parse_row_with_mapping(
    row: Dict[str, Any],
    row_idx: int,
    mapping: Dict[str, Optional[str]],
    is_strict_template: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    # 1. SKU / external_id
    raw_sku = str(row.get(mapping["external_id"], "") or "").strip() if mapping["external_id"] else ""
    if not raw_sku:
        if is_strict_template:
            return None, "Missing required external_id (SKU)"
        raw_sku = f"KAG-{1000 + row_idx}"
    sku = raw_sku[:64]

    # 2. Title
    title = str(row.get(mapping["title"], "") or "").strip() if mapping["title"] else ""
    if not title:
        return None, "Missing product title"

    # 3. Price (handles "$1,299.50", "₹7,999", etc.)
    raw_price = str(row.get(mapping["price"], "") or "").strip() if mapping["price"] else ""
    cleaned_price = re.sub(r"[^\d.]", "", raw_price)
    # Guard against multiple dots like "1.299.00"
    if cleaned_price.count(".") > 1:
        parts = cleaned_price.split(".")
        cleaned_price = "".join(parts[:-1]) + "." + parts[-1]
    try:
        price = float(cleaned_price)
        if price <= 0:
            raise ValueError()
    except ValueError:
        return None, f"Invalid price ('{raw_price or 'EMPTY'}') — must be > 0.00"

    # 4. Category
    raw_cat = str(row.get(mapping["category"], "") or "").strip() if mapping["category"] else ""
    raw_cat = raw_cat.strip('[]"')
    category = re.split(r"[>|/\\]", raw_cat)[0].strip()[:100] if raw_cat else "General"
    if not category:
        category = "General"

    # 5. Brand
    brand = str(row.get(mapping["brand"], "") or "").strip() if mapping["brand"] else ""
    brand = brand[:100] if brand else "Generic"

    # 6. Stock status
    raw_stock = str(row.get(mapping["stock_status"], "IN_STOCK") or "IN_STOCK").strip().upper() if mapping["stock_status"] else "IN_STOCK"
    stock = raw_stock if raw_stock in {"IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK"} else "IN_STOCK"

    # 7. Image & Description
    image_url = str(row.get(mapping["image_url"], "") or "").strip() if mapping["image_url"] else None
    if image_url and not image_url.startswith("http"):
        image_url = None
    description = str(row.get(mapping["description"], "") or "").strip() if mapping["description"] else None

    # 8. Extract extra Kaggle columns as dynamic attributes
    attributes: Dict[str, str] = {}
    used_cols = set(mapping.values())
    for k, v in row.items():
        if k and k not in used_cols and k.lower().strip() in EXTRA_ATTRIBUTE_HINTS:
            val = str(v or "").strip()
            if val and val.lower() not in {"nan", "none", "null", "na"}:
                attributes[k.lower().strip()[:64]] = val[:255]

    return {
        "external_id": sku,
        "title": title[:255],
        "description": description[:2000] if description else None,
        "category": category,
        "brand": brand,
        "price": round(price, 2),
        "stock_status": stock,
        "image_url": image_url[:500] if image_url else None,
        "attributes": attributes,
    }, None