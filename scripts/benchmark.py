"""Only report paired efficiency when ten accepted manual/automated tasks exist."""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median

FIELDS=["task_id","manual_active_s","automated_active_s","manual_wall_s","automated_wall_s","manual_quality","automated_quality","errors","corrections"]


def summarize(path):
    rows=list(csv.DictReader(Path(path).open(encoding="utf-8",newline="")))
    accepted=[]
    for row in rows:
        try:
            times=[float(row[k]) for k in FIELDS[1:5]]
            if any(not math.isfinite(t) or t<=0 for t in times) or row["manual_quality"]!="pass" or row["automated_quality"]!="pass":continue
            accepted.append(times)
        except (ValueError,KeyError):continue
    if len({r["task_id"] for r in rows})!=len(rows):
        raise ValueError("Duplicate paired task IDs")
    if len(accepted)<10:return {"state":"insufficient_manual_evidence","accepted_pairs":len(accepted),"minimum_pairs":10}
    return {"state":"measured","accepted_pairs":len(accepted),
        "median_active_time_ratio":median(r[0]/r[1] for r in accepted),
        "median_wall_time_ratio":median(r[2]/r[3] for r in accepted),
        "interpretation":"Paired equal-quality task timing; not a sales or revenue improvement."}


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("csv");p.add_argument("--create-template",action="store_true");a=p.parse_args()
    if a.create_template:
        path=Path(a.csv);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("x",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader()
            writer.writerows({"task_id":f"task-{i:02d}"} for i in range(1,11))
    else:print(json.dumps(summarize(a.csv),indent=2))
