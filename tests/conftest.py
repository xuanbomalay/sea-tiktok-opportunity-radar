import pytest
from radar.config import load_config
from radar.parsing import normalize
from scripts.make_demo import demo_envelopes


@pytest.fixture
def config():
    return load_config()


@pytest.fixture(scope="session")
def records():
    result=[]
    for env in demo_envelopes(days=96,per_group=3):
        for row in env["rows"]:
            result.append(normalize(row,country=env["country"],niche=env["niche"],query=env["query"],
                collected_at=env["observed_at"],source=env["source"],run_id=env["run_id"]))
    return result
