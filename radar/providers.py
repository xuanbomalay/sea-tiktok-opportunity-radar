"""REST client with bounded costs and no automatic replay of ambiguous POSTs."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    pass


class Apify:
    base = "https://api.apify.com/v2"

    def __init__(self, token=None, sleep=time.sleep):
        self.token = token or os.environ.get("APIFY_TOKEN", "")
        self.sleep = sleep
        if not self.token:
            raise ProviderError("missing_apify_token")

    def request(self, path, *, method="GET", payload=None, retries=2):
        # The token stays in a header and is never included in logged URLs/errors.
        for attempt in range(retries + 1 if method == "GET" else 1):
            try:
                request = Request(self.base + path, method=method,
                    data=json.dumps(payload).encode() if payload is not None else None,
                    headers={"Authorization": "Bearer " + self.token,
                             "Content-Type": "application/json", "User-Agent": "SEA-Radar/0.1"})
                with urlopen(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                code = error.code
                if method == "GET" and (code == 429 or code >= 500) and attempt < retries:
                    self.sleep(min(2**attempt, 8))
                    continue
                raise ProviderError(f"http_{code}") from None
            except (URLError, TimeoutError, OSError):
                if method == "GET" and attempt < retries:
                    self.sleep(min(2**attempt, 8))
                    continue
                raise ProviderError("ambiguous_start" if method == "POST" else "network_error") from None
            except (json.JSONDecodeError, ValueError):
                raise ProviderError("invalid_provider_json") from None

    @staticmethod
    def body(actor, country, query, limit):
        if actor.startswith("coregent/"):
            return {"keywords": [query], "countries": [country],
                    "maxResultsPerQuery": limit, "maxResultsTotal": limit,
                    "includeProductDetails": False, "includeReviews": False,
                    "includeSummary": False, "deduplicateProducts": True}
        # Adapter contract is documented and contract-tested separately.
        return {"mode": "search", "region": country.lower(), "search_keywords": [query],
                "max_items": limit}

    def start(self, actor, country, query, limit, cost_cap):
        query_params = urlencode({"waitForFinish": 0, "timeout": 240,
                                  "maxTotalChargeUsd": round(cost_cap, 6)})
        return self.request(f"/acts/{actor.replace('/', '~')}/runs?{query_params}",
            method="POST", payload=self.body(actor, country, query, limit))["data"]

    def poll(self, run_id, timeout, interval):
        deadline = time.monotonic() + timeout
        while True:
            run = self.request(f"/actor-runs/{run_id}")["data"]
            if run["status"] in {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}:
                return run
            if time.monotonic() >= deadline:
                raise ProviderError("pending_run")
            self.sleep(interval)

    def items(self, dataset_id, limit):
        data = self.request(f"/datasets/{dataset_id}/items?" + urlencode(
            {"format": "json", "clean": "false", "limit": limit + 2}))
        if not isinstance(data, list):
            raise ProviderError("dataset_not_a_list")
        return data
