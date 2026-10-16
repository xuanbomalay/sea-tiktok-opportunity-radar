import copy
from types import SimpleNamespace as NS
import pytest
from radar.agent import report
from radar.analysis import snapshot
from radar.render import validate_public,build_site


def test_no_credentials_is_labeled_rule_report(records,config,monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    s=snapshot(records,config,synthetic=True)
    result,brief=report(s,config)
    assert result['state']=='rule_based' and result['calls']==0
    assert 'SYNTHETIC' in brief
    assert 'real sales' not in brief


def test_real_tool_agent_finalizes_only_known_evidence(records,config):
    from google.genai import types
    class Model:
        calls=0
        def generate_content(self,**kwargs):
            self.calls+=1
            fc=types.FunctionCall(name='query_metrics',args={'country':'MY'}) if self.calls==1 else types.FunctionCall(name='finalize_report',args={'evidence_ids':['MY:storage'],'next_steps':['inspect_coverage']})
            return NS(candidates=[NS(content=types.Content(role='model',parts=[types.Part(function_call=fc)]))])
    model=Model()
    result,brief=report(snapshot(records,config),config,client=NS(models=model))
    assert result['state']=='agent_completed'
    assert result['calls']==model.calls==2
    assert result['evidence_ids']==['MY:storage']
    assert '[MY:storage]' in brief


def test_invalid_evidence_cannot_publish_model_claims(records,config):
    from google.genai import types
    class Model:
        calls=0
        def generate_content(self,**kwargs):
            self.calls+=1
            return NS(candidates=[NS(content=types.Content(role='model',parts=[types.Part(function_call=types.FunctionCall(name='finalize_report',args={'evidence_ids':['FAKE:4x'],'next_steps':['collect_history']}))]))])
    model=Model();result,brief=report(snapshot(records,config),config,client=NS(models=model))
    assert model.calls==5
    assert result['state']=='rule_based'
    assert 'FAKE:4x' not in brief
    assert all(turn['error']=='invalid_evidence_or_step' for turn in result['trace'])


def test_secret_or_raw_metadata_is_rejected(config):
    s=snapshot([],config)
    s['secret']='apify_api_fake'
    with pytest.raises(ValueError):validate_public(s)
    s=snapshot([],config);s['source_run_id']='private'
    with pytest.raises(ValueError):validate_public(s)


def test_empty_site_can_be_built_without_fabricated_data(tmp_path,config):
    s=snapshot([],config)
    out=build_site(s,'No real observations.',tmp_path/'site',export_images=False)
    assert (out/'index.html').exists()
    assert (out/'assets/plotly.min.js').stat().st_size>100000
    import json
    data=json.loads((out/'data/latest.json').read_text())
    assert data['summary']['observations']==0
    assert data['products']==[]
    assert not data['synthetic']


def test_exhausted_daily_agent_budget_is_visible_without_another_call(tmp_path,monkeypatch):
    import json
    import radar.cli as cli
    from radar.storage import atomic_json,utc_now
    state=tmp_path/'state'
    atomic_json(state/'agent_daily_budget.json',{'date':utc_now()[:10],'total_calls':5})
    monkeypatch.setattr(cli,'report',lambda *a,**k: ({'state':'rule_based','calls':0,'evidence_ids':[],
        'next_steps':[],'trace':[],'reason':'disabled'},'Rule report.'))
    captured={}
    def capture(snapshot,brief,output,**kwargs):
        captured.update(snapshot=snapshot,brief=brief)
        return output
    monkeypatch.setattr(cli,'build_site',capture)
    assert cli.main(['bootstrap','--state-dir',str(state),'--output',str(tmp_path/'site'),'--no-images'])==0
    agent=captured['snapshot']['agent']
    assert agent['reason']=='daily_call_limit'
    assert agent['calls']==0 and agent['daily_calls_used']==agent['daily_call_limit']==5
    assert 'without another model request' in captured['brief']
    assert json.loads((state/'agent_daily_budget.json').read_text())['total_calls']==5
