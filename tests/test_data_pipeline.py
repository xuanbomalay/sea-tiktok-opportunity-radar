import copy
import json
import subprocess
from pathlib import Path
import pytest
from radar.parsing import parse_count,normalize,safe_product_url
from radar.storage import Store
from radar.collection import collect,import_replay
from radar.providers import ProviderError,Apify
from radar.cli import ensure_domain


@pytest.mark.parametrize('value,count,precision',[(0,0,'exact'),('1,234',1234,'exact'),('100',100,'exact'),('1K+',None,'lower_bound'),('1.2K',None,'unverified'),(None,None,'missing'),(-2,None,'unverified'),(True,None,'missing'),('0 sold',0,'exact')])
def test_conservative_count_parsing(value,count,precision):
    parsed=parse_count(value)
    assert parsed['sold_count']==count
    assert parsed['sold_precision']==precision


def test_market_schema_and_safe_links():
    args=dict(country='MY',niche='pets',query='pet',collected_at='2026-10-16T01:23:00Z',source='vendor',run_id='run')
    with pytest.raises(ValueError):normalize({'productId':'1','title':'p','country':'US'},**args)
    with pytest.raises(ValueError):normalize({'productId':'1','title':'p','currency':'USD'},**args)
    with pytest.raises(ValueError):normalize({'title':'missing id'},**args)
    assert safe_product_url('javascript:alert(1)')==''
    assert safe_product_url('https://evil.com/?tiktok.com')==''
    assert safe_product_url('https://shop.tiktok.com/my/pdp/test?token=secret')=='https://shop.tiktok.com/my/pdp/test'


def test_budget_is_atomic_idempotent_and_not_refunded(tmp_path):
    store=Store(tmp_path)
    assert store.reserve('same','2026-10',500,2)
    assert not store.reserve('same','2026-10',500,2)
    store.update_call('same','empty',rows=0,cost=0)
    assert store.budget('2026-10')=={'reserved_rows':500,'reserved_usd':2}
    store.reserve('other','2026-10',500,2)
    with pytest.raises(ValueError,match='budget_exhausted'):store.reserve('over','2026-10',1,.001)
    assert store.reserve('nextmonth','2026-11',1,.01)


class FakeApify:
    def __init__(self,ambiguous=False):self.started=[];self.ambiguous=ambiguous
    def start(self,actor,country,query,limit,cost_cap):
        self.started.append((actor,country,query,limit,cost_cap))
        if self.ambiguous:raise ProviderError('ambiguous_start')
        return {'id':str(len(self.started)),'defaultDatasetId':str(len(self.started))}
    def poll(self,run_id,timeout,interval):
        return {'id':run_id,'status':'SUCCEEDED','defaultDatasetId':run_id,'finishedAt':'2026-10-16T01:23:30Z','usageTotalUsd':.004}
    def items(self,dataset_id,limit):
        country=self.started[int(dataset_id)-1][1]
        return [{'productId':'one','productTitle':'public sample','countryCode':country,'soldCount':12,'salePrice':3,'sellerId':'s'}]


def test_same_day_rerun_neither_recollects_nor_duplicates(tmp_path,config):
    client=FakeApify();store=Store(tmp_path)
    first=collect(store,config,client,now='2026-10-16T01:23:00Z')
    second=collect(store,config,client,now='2026-10-16T03:00:00Z')
    assert first['state']==second['state']=='ok'
    assert len(client.started)==9
    assert len(store.observations())==9
    assert all(q['reused'] for q in second['queries'])
    assert (tmp_path/'observations.parquet').exists()
    assert (tmp_path/'analytics.duckdb').exists()


def test_ambiguous_start_is_never_repeated(tmp_path,config):
    client=FakeApify(ambiguous=True);store=Store(tmp_path)
    collect(store,config,client,now='2026-10-16T01:23:00Z')
    before=len(client.started)
    second=collect(store,config,client,now='2026-10-16T02:00:00Z')
    assert len(client.started)==before
    assert all(q['state']=='manual_reconciliation_required' for q in second['queries'])
    assert store.budget('2026-10')['reserved_rows']==27


def test_synthetic_isolation(tmp_path):
    store=Store(tmp_path/'live');ensure_domain(store,False)
    with pytest.raises(ValueError,match='mix'):ensure_domain(store,True)
    fixture=tmp_path/'fixture.json';fixture.write_text(json.dumps([{'synthetic':True,'country':'MY','niche':'pets','query':'pets','source':'fixture','run_id':'demo','observed_at':'2026-01-01T00:00:00Z','rows':[]}]))
    with pytest.raises(ValueError,match='Synthetic'):import_replay(store,fixture)


def test_provider_disables_paid_enrichment():
    body=Apify.body('coregent/tiktok-shop-product-scraper','MY','pets',3)
    assert not body['includeReviews'] and not body['includeProductDetails']
    assert body['maxResultsTotal']==3


def test_fallback_uses_documented_input_contract():
    assert Apify.body('tictechid/vanzi-tiktok-shop','TH','pets',3)=={
        'mode':'search','region':'th','search_keywords':['pets'],'max_items':3}


def test_reservation_race_never_starts_second_vendor_call(tmp_path,config,monkeypatch):
    store=Store(tmp_path);client=FakeApify()
    monkeypatch.setattr(store,'reserve',lambda *a,**k:False)
    status=collect(store,config,client,now='2026-10-16T01:23:00Z')
    assert client.started==[]
    assert all(q['state']=='concurrent_reservation_reused' for q in status['queries'])


def test_daily_cap_is_checked_inside_transaction(tmp_path):
    store=Store(tmp_path)
    store.reserve('2026-10-16|a','2026-10',3,.014,day_cap=3)
    with pytest.raises(ValueError,match='daily_budget_exhausted'):
        store.reserve('2026-10-16|b','2026-10',3,.014,day_cap=3)


def test_http_retries_are_bounded_and_starts_are_not_repeated(monkeypatch):
    from urllib.error import HTTPError
    import radar.providers as provider
    calls=[]
    def fail(*a,**k):
        calls.append(1)
        raise HTTPError('https://api.apify.com/test',429,'limit',{},None)
    monkeypatch.setattr(provider,'urlopen',fail)
    client=Apify(token='FAKE_TOKEN_FOR_TEST_ONLY',sleep=lambda _:None)
    with pytest.raises(ProviderError,match='http_429'):client.request('/test')
    assert len(calls)==3
    calls.clear()
    with pytest.raises(ProviderError,match='http_429'):client.request('/test',method='POST',payload={})
    assert len(calls)==1


def test_get_failure_resumes_existing_run_without_new_post(tmp_path,config):
    class Flaky(FakeApify):
        recovered=False
        def poll(self,*args):
            if not self.recovered:raise ProviderError('network_error')
            return super().poll(*args)
    store=Store(tmp_path);client=Flaky()
    first=collect(store,config,client,now='2026-10-16T01:23:00Z')
    assert first['state']=='failed' and len(client.started)==9
    client.recovered=True
    second=collect(store,config,client,now='2026-10-16T02:00:00Z')
    assert second['state']=='ok' and len(client.started)==9


def test_workflow_rerun_loads_remote_history_before_budget_or_api(tmp_path,config,monkeypatch):
    """Reproduce Actions rerunning an old SHA after earlier state commits."""
    def git(*args,cwd=None):
        return subprocess.run(['git',*map(str,args)],cwd=cwd,check=True,capture_output=True)
    remote=tmp_path/'origin.git'
    writer=tmp_path/'writer';writer.mkdir()
    git('init','--bare','--initial-branch=main',remote)
    git('init','--initial-branch=main',cwd=writer)
    git('config','user.name','Radar test',cwd=writer)
    git('config','user.email','radar-test@example.invalid',cwd=writer)
    (writer/'README.md').write_text('Test fixture repository',encoding='utf-8')
    git('add','README.md',cwd=writer);git('commit','-m','Initial state',cwd=writer)
    git('remote','add','origin',remote,cwd=writer);git('push','origin','main',cwd=writer)
    runner=tmp_path/'runner';git('clone',remote,runner)
    git('config','user.name','Radar test',cwd=runner)
    git('config','user.email','radar-test@example.invalid',cwd=runner)
    first_store=Store(writer/'private')
    first=collect(first_store,config,FakeApify(),now='2026-10-16T01:23:00Z')
    assert first['state']=='ok'
    git('add','private',cwd=writer);git('commit','-m','Persist collected history',cwd=writer)
    git('push','origin','main',cwd=writer)
    monkeypatch.setenv('RADAR_GIT_CHECKPOINT','true')
    restored=Store(runner/'private')
    client=FakeApify()
    second=collect(restored,config,client,now='2026-10-16T03:00:00Z')
    assert second['state']=='ok' and client.started==[]
    assert len(restored.observations())==9
    assert restored.budget('2026-10')==first['budget']
    assert all(query['reused'] for query in second['queries'])
    restored.checkpoint()
    (runner/'README.md').write_text('Uncommitted work must be preserved',encoding='utf-8')
    with pytest.raises(ValueError,match='checkpoint_checkout_not_clean'):
        Store(runner/'private')
