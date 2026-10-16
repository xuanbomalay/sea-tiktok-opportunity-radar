from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = {"MY": "Malaysia", "TH": "Thailand", "VN": "Vietnam"}
CURRENCIES = {"MY": "MYR", "TH": "THB", "VN": "VND"}


def load_config(path=None):
    with open(path or ROOT / "config.toml", "rb") as stream:
        config = tomllib.load(stream)
    c = config["collection"]
    if not set(c["countries"]) <= COUNTRIES.keys():
        raise ValueError("Unsupported country")
    if not (0 < c["monthly_usd"] <= 4 and 0 < c["monthly_results"] <= 1000):
        raise ValueError("Free-only budget must not exceed $4 / 1000 results")
    if not (0 < c["daily_results"] <= 27 and 0 < c["results_per_query"] <= 3):
        raise ValueError("Initial sample cap is 27 results/day, 3/query")
    if not 0 < config["agent"]["max_calls"] <= 5:
        raise ValueError("Agent call cap must be 1..5")
    return config
