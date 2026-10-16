import copy
import math
import pandas as pd
from radar.analysis import panel,snapshot
from radar.modeling import training_frame,split_mature,evaluate


def test_exact_calendar_pairs_not_row_shifts(records):
    rows=[r for r in records if r['country']=='MY' and r['niche']=='storage' and r['product_id'].endswith('-0')]
    rows=[r for r in rows if r['date']!='2026-01-08']
    f=panel(rows)
    assert pd.isna(f.loc[f.date=='2026-01-15','increment7'].iloc[0])
    assert f.loc[f.date=='2026-01-16','increment7'].iloc[0]>=0


def test_counter_reset_and_provider_changes_are_not_sales(records):
    rows=copy.deepcopy(records[:])
    last=max(r['date'] for r in rows)
    for r in rows:
        if r['date']==last:r['sold_count']=0
    f=panel(rows)
    assert f[f.date==last].increment7.isna().all()
    changed=copy.deepcopy(records)
    for r in changed:
        if r['date']==last:r['source']='different_provider'
    f=training_frame(changed)
    assert f[f.date==last].increment7.isna().all()


def test_label_maturity_is_purged(records):
    train,val,test=split_mature(training_frame(records))
    assert train.target_end.max()<val.day.min()
    assert val.target_end.max()<test.day.min()
    assert not set(train.date)&set(val.date)
    assert not set(val.date)&set(test.date)


def test_missing_market_preserves_last_good_sample(records,config):
    last=max(r['date'] for r in records)
    rows=[r for r in records if not(r['date']==last and r['country']=='TH')]
    s=snapshot(rows,config,synthetic=True)
    thai=[g for g in s['groups'] if g['country']=='TH']
    assert all(g['sample_products']==3 for g in thai)
    assert all(g['as_of_date']<last for g in thai)


def test_growth_uses_three_way_matched_panel(records,config):
    s=snapshot(records,config,synthetic=True)
    for g in s['groups']:
        assert g['matched_products']==3
        assert g['growth7'] is not None
        assert 0<g['competition_proxy']<=1
    assert s['synthetic'] and s['data_mode']=='synthetic_demo'


def test_model_waits_without_history(config):
    result=evaluate([],config)
    assert result['state']=='history_accumulating'
    assert result['mature_labels']==0
    assert 'test_metrics' not in result


def test_models_are_evaluated_and_selected_on_validation(records,config):
    report=evaluate(records,config,synthetic=True)
    assert report['state']=='evaluated'
    assert report['synthetic']
    assert report['selected_model']==min(report['validation_mae'],key=report['validation_mae'].get)
    assert set(report['test_metrics'])=={'recent_mean','ridge','gradient_boosting'}
    assert all(math.isfinite(m['mae']) and m['mae']>=0 for m in report['test_metrics'].values())
    assert report['forecasts']
    assert report['split']['train']['last_label_end']<report['split']['validation']['first_date']
