import gzip
import hashlib
import json
import sqlite3
import os
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        if os.environ.get("RADAR_GIT_CHECKPOINT") == "true":
            self.sync_checkpoint_state()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "ledger.sqlite3"
        with closing(self.connect()) as con:
            con.executescript('''
              CREATE TABLE IF NOT EXISTS calls (
                key TEXT PRIMARY KEY, month TEXT, status TEXT, reserved_rows INTEGER,
                reserved_microusd INTEGER, run_id TEXT, dataset_id TEXT, actual_rows INTEGER,
                actual_microusd INTEGER, updated_at TEXT);
              CREATE TABLE IF NOT EXISTS observations (
                date TEXT, country TEXT, niche TEXT, product_id TEXT, payload TEXT,
                PRIMARY KEY(date,country,niche,product_id));
            ''')
            con.commit()

    def connect(self):
        return sqlite3.connect(self.database, timeout=30)

    def sync_checkpoint_state(self):
        """A workflow rerun must read today's ledger, not its original commit."""
        repo = self.root.parent
        if not (repo / ".git").exists() or self.root.name != "private":
            raise ValueError("checkpoint_repository_invalid")
        status = subprocess.run(["git","status","--porcelain"],cwd=repo,capture_output=True,timeout=60)
        if status.returncode or status.stdout.strip():
            raise ValueError("checkpoint_checkout_not_clean")
        for args in (["git","fetch","origin","main"], ["git","merge","--ff-only","FETCH_HEAD"]):
            done = subprocess.run(args,cwd=repo,capture_output=True,timeout=60)
            if done.returncode:
                raise ValueError("checkpoint_history_sync_failed")

    def checkpoint(self):
        """Persist the budget before an external side effect on ephemeral runners."""
        if os.environ.get("RADAR_GIT_CHECKPOINT") != "true":
            return
        repo = self.root.parent
        if not (repo / ".git").exists() or self.root.name != "private":
            raise ValueError("checkpoint_repository_invalid")
        for args in (["git","add","private"], ["git","commit","--allow-empty","-m","Checkpoint collection budget and state"],
                     ["git","push","origin","HEAD:main"]):
            done = subprocess.run(args,cwd=repo,capture_output=True,timeout=60)
            if done.returncode:
                raise ValueError("checkpoint_failed")

    def get_call(self, key):
        with closing(self.connect()) as con:
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT * FROM calls WHERE key=?", (key,)).fetchone()
            return dict(row) if row else None

    def budget(self, month):
        with closing(self.connect()) as con:
            rows, money = con.execute('''SELECT COALESCE(SUM(reserved_rows),0),
                COALESCE(SUM(reserved_microusd),0) FROM calls WHERE month=?''', (month,)).fetchone()
        return {"reserved_rows": rows, "reserved_usd": money / 1000000}

    def reserve(self, key, month, rows, usd, *, row_cap=1000, usd_cap=4, day_cap=None):
        if rows <= 0 or usd <= 0:
            raise ValueError("invalid_budget_reservation")
        money = int(Decimal(str(usd)) * 1000000)
        with closing(self.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT key FROM calls WHERE key=?", (key,)).fetchone()
            if old:
                return False
            if day_cap is not None:
                daily = con.execute("SELECT COALESCE(SUM(reserved_rows),0) FROM calls WHERE key LIKE ?",(key[:10]+"|%",)).fetchone()[0]
                if daily + rows > day_cap:
                    raise ValueError("daily_budget_exhausted")
            used = con.execute('''SELECT COALESCE(SUM(reserved_rows),0),
                COALESCE(SUM(reserved_microusd),0) FROM calls WHERE month=?''', (month,)).fetchone()
            if used[0] + rows > row_cap or used[1] + money > int(Decimal(str(usd_cap))*1000000):
                raise ValueError("budget_exhausted")
            con.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (key, month, "reserved", rows, money, None, None, None, None, utc_now()))
            con.commit()
        self.checkpoint()
        return True

    def update_call(self, key, status, *, run_id=None, dataset_id=None, rows=None, cost=None):
        with closing(self.connect()) as con:
            con.execute('''UPDATE calls SET status=?,run_id=COALESCE(?,run_id),
                dataset_id=COALESCE(?,dataset_id),actual_rows=COALESCE(?,actual_rows),
                actual_microusd=COALESCE(?,actual_microusd),updated_at=? WHERE key=?''',
                (status, run_id, dataset_id, rows, int(cost*1000000) if cost is not None else None, utc_now(), key))
            con.commit()
        self.checkpoint()
        # Reservations remain conservatively charged even on empty/failed/ambiguous runs.

    def add(self, records):
        with closing(self.connect()) as con:
            con.executemany("INSERT INTO observations VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                [(r["date"],r["country"],r["niche"],r["product_id"],json.dumps(r,ensure_ascii=False)) for r in records])
            con.commit()

    def observations(self):
        with closing(self.connect()) as con:
            return [json.loads(r[0]) for r in con.execute("SELECT payload FROM observations ORDER BY date,country,niche,product_id")]

    def save_raw(self, key, envelope):
        name = hashlib.sha256(key.encode()).hexdigest() + ".json.gz"
        path = self.root / "raw" / name
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                json.dump(envelope, stream, ensure_ascii=False)
        return path

    def export(self):
        import pandas as pd
        import duckdb
        rows = self.observations()
        if not rows:
            return
        frame = pd.DataFrame(rows)
        frame.to_parquet(self.root / "observations.parquet", index=False)
        with duckdb.connect(str(self.root / "analytics.duckdb")) as con:
            con.register("observed_frame", frame)
            con.execute("CREATE OR REPLACE TABLE observations AS SELECT * FROM observed_frame")
