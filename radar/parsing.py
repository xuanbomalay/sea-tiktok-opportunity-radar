"""Conservative vendor adapters: never turn rounded display counts into labels."""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from .config import CURRENCIES


def finite_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(str(value).replace(",", ""))
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


def parse_count(value):
    raw = "" if value is None else str(value).strip()
    if not raw or isinstance(value, bool):
        return {"sold_raw": raw, "sold_count": None, "sold_precision": "missing"}
    text = re.sub(r"\s*(sold|sales|已售)\s*", "", raw, flags=re.I).strip()
    if re.fullmatch(r"\d+|\d{1,3}(?:,\d{3})+", text):
        count = int(text.replace(",", ""))
        if count <= 2**53:
            return {"sold_raw": raw, "sold_count": count, "sold_precision": "exact"}
    # Keep only a reference lower bound for '+'; rounded values are not exact.
    match = re.fullmatch(r"([\d.]+)\s*([KkMm万千]?)\s*(\+?)", text)
    lower = None
    if match:
        scale = {"k": 1000, "m": 1000000, "万": 10000, "千": 1000, "": 1}
        n = finite_number(match[1])
        if n is not None:
            lower = n * scale[match[2].lower()]
    return {"sold_raw": raw, "sold_count": None,
            "sold_precision": "lower_bound" if text.endswith("+") else "unverified",
            "sold_reference": lower}


def first(row, *keys):
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return None


def safe_product_url(value):
    try:
        p = urlparse(str(value or ""))
        if p.scheme == "https" and (p.hostname == "tiktok.com" or (p.hostname or "").endswith(".tiktok.com")):
            return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except ValueError:
        pass
    return ""


def normalize(row, *, country, niche, query, collected_at, source, run_id):
    if not isinstance(row, dict):
        raise ValueError("schema: row is not an object")
    instant = datetime.fromisoformat(collected_at)
    if instant.tzinfo is None:
        raise ValueError("schema: observation time requires a timezone")
    collected_at = instant.astimezone(timezone.utc).isoformat(timespec="seconds")
    product_id = first(row, "productId", "product_id", "id")
    title = first(row, "productTitle", "title", "product_name", "name")
    if not product_id or not title:
        raise ValueError("schema: product id/title missing")
    returned_country = first(row, "countryCode", "country", "region")
    if returned_country and str(returned_country).upper() != country:
        raise ValueError("schema: country does not match requested market")
    currency = first(row, "currency", "currencyCode")
    if currency and currency not in (CURRENCIES[country], {"MY": "RM", "TH": "฿", "VN": "₫"}[country]):
        raise ValueError("schema: currency does not match market")
    seller = first(row, "sellerId", "seller_id", "sellerName", "seller_name", "shop_name")
    if isinstance(row.get("seller"), dict):
        seller = seller or first(row["seller"], "id", "name")
    record = {
        "observed_at": collected_at, "date": collected_at[:10], "country": country,
        "niche": niche, "query": query, "product_id": str(product_id),
        "title": str(title)[:400], "seller_id": str(seller) if seller is not None else None,
        "price": finite_number(first(row, "salePrice", "price", "sale_price")),
        "currency": CURRENCIES[country],
        "rating": finite_number(first(row, "ratingAverage", "rating", "rating_average")),
        "url": safe_product_url(first(row, "productUrl", "product_url", "url")),
        "source": source, "source_run_id": run_id,
        "raw_sha256": hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        **parse_count(first(row, "soldCount", "sold_count", "sold", "sales")),
    }
    if record["rating"] is not None and record["rating"] > 5:
        raise ValueError("schema: rating outside 0..5")
    return record
