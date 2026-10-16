"""Generate conspicuously synthetic fixtures; never run as a production collector."""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.config import load_config, CURRENCIES


def demo_envelopes(days=96, per_group=6):
    rng = random.Random(42)
    config = load_config()
    counters = {}
    envelopes = []
    for t in range(days):
        day = date(2026,1,1)+timedelta(days=t)
        for ci,country in enumerate(config["collection"]["countries"]):
            for ni,(niche,query) in enumerate(config["queries"].items()):
                rows = []
                for item in range(per_group):
                    key = (country,niche,item)
                    counters[key] = counters.get(key,100+item*20)+max(0,int(3+ci+ni+item+t*.04*(ni+1)+rng.gauss(0,2)))
                    rows.append({"productId":f"DEMO-{country}-{niche}-{item}",
                        "productTitle":f"SYNTHETIC {query['label']} sample {item+1}",
                        "sellerId":f"DEMO-{country}-{niche}-seller-{item%4}",
                        "countryCode":country,"currency":CURRENCIES[country],
                        "salePrice":round((15+item*3)*{"MY":1,"TH":8,"VN":6000}[country],2),
                        "soldCount":counters[key],"ratingAverage":round(4+item*.1,1),"productUrl":""})
                envelopes.append({"synthetic":True,"country":country,"niche":niche,"query":query[country],
                    "source":"synthetic_fixture","run_id":f"DEMO-{day}-{country}-{niche}",
                    "observed_at":str(day)+"T01:23:00+00:00","rows":rows})
    return envelopes


if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",default="artifacts/synthetic.json")
    a=p.parse_args();dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(demo_envelopes(),ensure_ascii=False),encoding="utf-8")
    print("Synthetic fixtures written. These are NOT real market observations.")
