import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from datetime import date, timedelta
from .config import load_config
from .storage import Store, atomic_json, utc_now
from .collection import collect, import_replay
from .analysis import snapshot
from .modeling import evaluate
from .agent import report
from .render import build_site


def ensure_domain(store, synthetic):
    marker = store.root / "domain.json"
    expected = "synthetic" if synthetic else "live"
    if marker.exists() and json.loads(marker.read_text(encoding="utf-8"))["domain"] != expected:
        raise ValueError("Refusing to mix synthetic and live state")
    atomic_json(marker,{"domain":expected})


def main(argv=None):
    parser = argparse.ArgumentParser(description="SEA TikTok Opportunity Radar")
    sub = parser.add_subparsers(dest="command",required=True)
    for name in ("run","replay","evaluate","bootstrap"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config")
        cmd.add_argument("--state-dir",default=None)
        cmd.add_argument("--output",default="dist")
        if name in {"replay","evaluate"}:
            cmd.add_argument("--synthetic",action="store_true")
        if name == "replay":
            cmd.add_argument("input")
        if name != "evaluate":
            cmd.add_argument("--no-agent",action="store_true")
            cmd.add_argument("--no-images",action="store_true",help="Skip PNG export; not a full visual acceptance run")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    synthetic = getattr(args,"synthetic",False)
    default_state = "artifacts/synthetic-state" if synthetic else "private"
    store = Store(args.state_dir or default_state)
    ensure_domain(store,synthetic)
    attempt_path = store.root / "last_attempt.json"
    attempt = json.loads(attempt_path.read_text(encoding="utf-8")) if attempt_path.exists() else None
    if args.command == "run":
        attempt = collect(store,config)
    elif args.command == "replay":
        import_replay(store,args.input,synthetic=synthetic)
        attempt = {"state":"replayed_synthetic" if synthetic else "replayed", "attempted_at":utc_now(),
                   "countries":{c:"replayed" for c in config["collection"]["countries"]}}
    records = store.observations()
    evaluation = evaluate(records,config,synthetic=synthetic)
    atomic_json(store.root/"evaluation.json",evaluation)
    if args.command == "evaluate":
        print(json.dumps(evaluation,ensure_ascii=False,allow_nan=False))
        return 0
    public = snapshot(records,config,attempt=attempt,synthetic=synthetic,evaluation=evaluation)
    history_path = store.root/"daily_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() and not synthetic else {}
    scheduled = [day for day,value in sorted(history.items()) if value["scheduled_success"]]
    streak = best_streak = 0
    previous = None
    for day in scheduled:
        current = date.fromisoformat(day)
        streak = streak+1 if previous is not None and current-previous == timedelta(days=1) else 1
        best_streak = max(best_streak,streak)
        previous = current
    public["operational_acceptance"] = {
        "manual_cloud_success":any(day["manual_cloud_success"] for day in history.values()),
        "successful_scheduled_dates":scheduled,
        "maximum_consecutive_scheduled_days":best_streak,
        "unattended_acceptance_verified":best_streak >= 3 and any(day["manual_cloud_success"] for day in history.values()),
        "required_scheduled_dates":3,
    }
    cache_path = store.root/"agent_daily.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    budget_path = store.root/"agent_daily_budget.json"
    agent_budget = json.loads(budget_path.read_text(encoding="utf-8")) if budget_path.exists() else {}
    day = utc_now()[:10]
    digest = hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    used = agent_budget.get("total_calls",0) if agent_budget.get("date") == day else 0
    daily_used = used
    if cache.get("date") == day and cache.get("data_hash") == digest and cache.get("agent",{}).get("state") == "agent_completed":
        agent, brief = cache["agent"], cache["brief"]
    else:
        bounded = copy.deepcopy(config)
        bounded["agent"]["max_calls"] = max(0,config["agent"]["max_calls"]-used)
        def checkpoint_attempt(attempt):
            atomic_json(budget_path,{"date":day,"total_calls":used+attempt})
            store.checkpoint()
        agent, brief = report(public,bounded,enabled=not args.no_agent and not synthetic and bounded["agent"]["max_calls"]>0,on_attempt=checkpoint_attempt)
        daily_used = used + agent["calls"]
        if not args.no_agent and not synthetic and bounded["agent"]["max_calls"] == 0:
            agent["reason"] = "daily_call_limit"
            brief += "\nAgent daily call limit reached; this rerun uses the rule-based report without another model request.\n"
        atomic_json(cache_path,{"date":day,"total_calls":used+agent["calls"],"data_hash":digest,"agent":agent,"brief":brief})
    agent["daily_calls_used"] = daily_used
    agent["daily_call_limit"] = config["agent"]["max_calls"]
    atomic_json(store.root/"agent_trace.json",agent)
    public["agent"] = {k:v for k,v in agent.items() if k != "trace"}
    output = build_site(public,brief,args.output,export_images=not args.no_images)
    print(json.dumps({"command":args.command,"data_mode":public["data_mode"],"observations":len(records),
        "collection":public["attempt"]["state"],"evaluation":evaluation["state"],
        "agent":agent["state"],"output":str(output),"png_exported":not args.no_images},ensure_ascii=False))
    return 2 if args.command == "run" and attempt["state"] in {"needs_credentials","failed"} else 0


if __name__ == "__main__":
    sys.exit(main())
