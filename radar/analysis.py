import hashlib
import pandas as pd
from .config import COUNTRIES
from .storage import utc_now

KEYS = ["country", "niche", "product_id", "source"]


def panel(records):
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records).copy()
    frame["day"] = pd.to_datetime(frame["date"])
    frame["exact"] = pd.to_numeric(frame["sold_count"], errors="coerce").where(frame["sold_precision"] == "exact")
    frame = frame.sort_values("observed_at").drop_duplicates(KEYS + ["date"], keep="first")
    for days in (7, 14):
        lag = frame[KEYS + ["day", "exact"]].copy()
        lag["day"] += pd.Timedelta(days=days)
        frame = frame.merge(lag.rename(columns={"exact": f"lag{days}"}), on=KEYS+["day"], how="left", validate="one_to_one")
    frame["increment7"] = (frame["exact"] - frame["lag7"]).where(frame["exact"] >= frame["lag7"])
    frame["previous7"] = (frame["lag7"] - frame["lag14"]).where(frame["lag7"] >= frame["lag14"])
    return frame


def number(value):
    return float(value) if pd.notna(value) else None


def snapshot(records, config, *, attempt=None, synthetic=False, evaluation=None):
    frame = panel(records)
    generated = utc_now()
    groups, trends, products = [], [], []
    latest_day = None if frame.empty else frame["day"].max()
    for country, country_name in COUNTRIES.items():
        for niche, spec in config["queries"].items():
            part = frame[(frame.country == country) & (frame.niche == niche)] if not frame.empty else pd.DataFrame()
            group_day = part.day.max() if not part.empty else latest_day
            latest = part[part.day == group_day] if not part.empty else part
            n = len(latest)
            sellers = latest.seller_id.dropna() if n else pd.Series(dtype=str)
            shares = sellers.value_counts(normalize=True)
            paired = latest.dropna(subset=["increment7", "previous7"]) if n else pd.DataFrame()
            recent = number(paired.increment7.sum()) if len(paired) else None
            prior = number(paired.previous7.sum()) if len(paired) else None
            growth = recent / prior - 1 if prior is not None and prior > 0 else None
            window = part[part.day >= group_day-pd.Timedelta(days=27)] if not part.empty else part
            observed_dates = int(window.day.nunique()) if len(window) else 0
            unique_products = int(window.product_id.nunique()) if len(window) else 0
            group = {
                "country": country, "country_name": country_name, "niche": niche, "label": spec["label"],
                "as_of_date": str(group_day.date()) if group_day is not None else None,
                "sample_products": n, "unique_products_28d": unique_products,
                "observed_dates_28d": observed_dates,
                "sample_sellers": int(sellers.nunique()) if len(sellers) else None,
                "seller_coverage": len(sellers)/n if n else None,
                "seller_hhi": number((shares**2).sum()) if len(shares) else None,
                "competition_proxy": sellers.nunique()/n if len(sellers) else None,
                "matched_products": len(paired), "increment7_proxy": recent,
                "growth7": growth,
                "median_price": number(latest.price.median()) if n else None,
                "currency": {"MY":"MYR","TH":"THB","VN":"VND"}[country],
                "confidence": "limited" if unique_products >= 20 and observed_dates >= 14 and len(paired) >= 3 and len(sellers) == n else "low" if n else "no_data",
            }
            groups.append(group)
            if not part.empty:
                for day, daily in part.groupby("date"):
                    trends.append({"country":country,"niche":niche,"date":day,
                        "median_price":number(daily.price.median()),
                        "median_sold_count":number(daily.exact.median()),"sample_products":len(daily)})
                for row in latest.to_dict("records"):
                    products.append({"country":country,"niche":niche,"title":row["title"],
                        "product_ref":hashlib.sha256((country+row["product_id"]).encode()).hexdigest()[:10],
                        "price":number(row["price"]),"currency":row["currency"],"rating":number(row["rating"]),
                        "sold_raw":row["sold_raw"],"sold_precision":row["sold_precision"],
                        "increment7_proxy":number(row["increment7"]),"url":row["url"],
                        "source":row["source"],"observed_at":row["observed_at"]})
    products.sort(key=lambda row: (row["increment7_proxy"] is not None, row["increment7_proxy"] or 0), reverse=True)
    return {
        "schema_version":1,"generated_at":generated,"synthetic":synthetic,
        "data_mode":"synthetic_demo" if synthetic else "live",
        "latest_observed_at":None if frame.empty else str(frame.observed_at.max()),
        "summary":{"observations":len(records),"observation_dates":0 if frame.empty else int(frame.day.nunique()),
            "markets_observed":0 if frame.empty else int(frame.country.nunique()),
            "latest_sample_products":sum(g["sample_products"] for g in groups)},
        "methodology":{
            "scope":"Keyword-search samples, not a census of TikTok Shop.",
            "demand":"Seven-day counter increments; growth uses the same products at t, t-7 and t-14.",
            "competition":"Distinct observed sellers / sampled listings. HHI uses listing shares, not market sales shares.",
            "limitations":["Search ranking and query language create selection bias.",
                "Rounded counts, counter resets, missing products and missing dates are not zero sales.",
                "Low seller diversity can indicate dominance by one seller, not an easy market.",
                "Prices are in local currencies; no cross-currency price ranking is performed."]},
        "groups":groups,"trends":trends,"products":products,
        "attempt":attempt or {"state":"not_started","countries":{}},
        "evaluation":evaluation or {"state":"history_accumulating","minimum_dates":84,"minimum_labels":500},
        "agent":{"state":"not_run","calls":0,"evidence_ids":[]},
    }
