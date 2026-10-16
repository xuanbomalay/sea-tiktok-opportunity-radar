import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from .parsing import normalize
from .providers import Apify, ProviderError
from .storage import atomic_json, utc_now


def collect(store, config, client=None, *, now=None):
    now = now or utc_now()
    local_day = datetime.fromisoformat(now).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    c = config["collection"]
    status = {"attempted_at": now, "scheduled_for": local_day + "T09:23:00+08:00",
              "trigger":os.environ.get("GITHUB_EVENT_NAME","local"),
              "state": "ok", "countries": {}, "queries": []}
    try:
        client = client or Apify()
    except ProviderError as error:
        status.update(state="needs_credentials", error=str(error))
        for country in c["countries"]:
            status["countries"][country] = "needs_credentials"
        atomic_json(store.root / "last_attempt.json", status)
        return status
    daily_reserved = 0
    with store.connect() as con:
        daily_reserved = con.execute("SELECT COALESCE(SUM(reserved_rows),0) FROM calls WHERE key LIKE ?", (local_day + "|%",)).fetchone()[0]
    for country in c["countries"]:
        country_states = []
        for niche, spec in config["queries"].items():
            query = spec[country]
            outcome = {"country": country, "niche": niche, "query": query, "state": "empty"}
            actors = [c["primary_actor"], c["fallback_actor"]]
            for actor in actors:
                key = "|".join((local_day, country, niche, actor))
                call = store.get_call(key)
                limit = c["results_per_query"]
                price = c["primary_usd_per_result"] if actor == actors[0] else c["fallback_usd_per_result"]
                ceiling = round(limit * price + 0.002, 6)
                try:
                    if call is None:
                        if daily_reserved + limit > c["daily_results"]:
                            outcome["state"] = "daily_budget_exhausted"
                            break
                        reserved = store.reserve(key, local_day[:7], limit, ceiling,
                            row_cap=c["monthly_results"], usd_cap=c["monthly_usd"],day_cap=c["daily_results"])
                        if not reserved:
                            outcome["state"] = "concurrent_reservation_reused"
                            break
                        daily_reserved += limit
                        # Persist the reservation BEFORE the side effect. Never retry an uncertain POST.
                        try:
                            run = client.start(actor, country, query, limit, ceiling)
                        except ProviderError as error:
                            store.update_call(key, "ambiguous" if str(error) == "ambiguous_start" else "start_failed")
                            raise
                        store.update_call(key, "started", run_id=run["id"], dataset_id=run.get("defaultDatasetId"))
                        call = store.get_call(key)
                    if call["status"] == "complete":
                        outcome.update(state="ok", rows=call["actual_rows"], reused=True)
                        break
                    if call["status"] in {"reserved", "ambiguous", "start_failed"}:
                        outcome["state"] = "manual_reconciliation_required"
                        break
                    if call["status"] in {"empty", "schema_error", "run_failed"}:
                        outcome["state"] = call["status"]
                        continue
                    run = client.poll(call["run_id"], c["timeout_seconds"], c["poll_seconds"])
                    actual_cost = run.get("usageTotalUsd")
                    if run["status"] != "SUCCEEDED":
                        store.update_call(key, "run_failed", cost=actual_cost)
                        outcome["state"] = "run_failed"
                        continue
                    dataset_id = run.get("defaultDatasetId") or call["dataset_id"]
                    rows = client.items(dataset_id, limit)
                    observed_at = run.get("finishedAt") or now
                    envelope = {"country": country, "niche": niche, "query": query,
                                "source": actor, "run_id": run["id"], "observed_at": observed_at,
                                "rows": rows}
                    store.save_raw(key, envelope)
                    records, rejected = [], 0
                    for row in rows:
                        try:
                            records.append(normalize(row, country=country, niche=niche, query=query,
                                collected_at=observed_at, source=actor, run_id=run["id"]))
                        except ValueError:
                            rejected += 1
                    records = records[:limit]
                    store.add(records)
                    state = "complete" if records else ("schema_error" if rejected else "empty")
                    store.update_call(key, state, dataset_id=dataset_id, rows=len(records), cost=actual_cost)
                    outcome.update(state="ok" if records else state, rows=len(records), rejected=rejected)
                    if records:
                        break
                except (ProviderError, ValueError) as error:
                    outcome["state"] = str(error)
                    # Do not change an uncertain external side effect into a second vendor start.
                    break
            status["queries"].append(outcome)
            country_states.append(outcome["state"])
        status["countries"][country] = "ok" if all(s == "ok" for s in country_states) else "partial" if "ok" in country_states else "failed"
    status["state"] = "ok" if all(s == "ok" for s in status["countries"].values()) else "partial" if "ok" in [q["state"] for q in status["queries"]] else "failed"
    status["budget"] = store.budget(local_day[:7])
    atomic_json(store.root / "last_attempt.json", status)
    history_path = store.root/"daily_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {}
    if status["state"] == "ok":
        day = history.setdefault(local_day,{"manual_cloud_success":False,"scheduled_success":False})
        day["manual_cloud_success"] |= status["trigger"] == "workflow_dispatch"
        day["scheduled_success"] |= status["trigger"] == "schedule"
    atomic_json(history_path,history)
    store.export()
    return status


def import_replay(store, input_path, *, synthetic=False):
    from pathlib import Path
    envelopes = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if isinstance(envelopes, dict):
        envelopes = [envelopes]
    if not isinstance(envelopes, list):
        raise ValueError("Replay input must be an envelope or envelope array")
    count = 0
    for envelope in envelopes:
        required = {"country", "niche", "query", "source", "run_id", "observed_at", "rows"}
        if not required <= envelope.keys():
            raise ValueError("Missing replay provenance fields")
        is_synthetic = envelope.get("synthetic", False)
        if bool(is_synthetic) != bool(synthetic):
            raise ValueError("Synthetic fixtures require --synthetic; live replay must not mix synthetic data")
        records = [normalize(row, country=envelope["country"], niche=envelope["niche"], query=envelope["query"],
                    source=envelope["source"], run_id=envelope["run_id"], collected_at=envelope["observed_at"])
                   for row in envelope["rows"]]
        store.add(records)
        count += len(records)
    store.export()
    return count
