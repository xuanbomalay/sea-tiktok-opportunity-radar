"""Forecast a displayed counter proxy, with chronological label-maturity purges."""
import hashlib
import json
import numpy as np
import pandas as pd
from .analysis import KEYS, panel

NUMERIC = ["increment7", "previous7", "log_price", "rating"]
CATEGORICAL = ["country", "niche"]


def training_frame(records):
    frame = panel(records)
    if frame.empty:
        return frame
    future = frame[KEYS+["day","exact"]].copy()
    future["day"] -= pd.Timedelta(days=7)
    frame = frame.merge(future.rename(columns={"exact":"future_count"}), on=KEYS+["day"], how="left", validate="one_to_one")
    frame["target"] = (frame.future_count-frame.exact).where(frame.future_count >= frame.exact)
    frame["target_end"] = frame.day + pd.Timedelta(days=7)
    frame["log_price"] = np.log1p(pd.to_numeric(frame.price, errors="coerce"))
    return frame


def split_mature(frame):
    labeled = frame.dropna(subset=["target","increment7"]).copy()
    dates = sorted(labeled.day.unique())
    if len(dates) < 15:
        return None
    val_start, test_start = pd.Timestamp(dates[int(len(dates)*.6)]), pd.Timestamp(dates[int(len(dates)*.8)])
    train = labeled[(labeled.day < val_start) & (labeled.target_end < val_start)]
    val = labeled[(labeled.day >= val_start) & (labeled.day < test_start) & (labeled.target_end < test_start)]
    test = labeled[labeled.day >= test_start]
    return train, val, test


def evaluate(records, config, *, synthetic=False):
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    settings = config["model"]
    frame = training_frame(records)
    dates = int(frame.day.nunique()) if not frame.empty else 0
    labeled = frame.dropna(subset=["target","increment7"]) if not frame.empty else frame
    report = {"state":"history_accumulating","synthetic":synthetic,"observation_dates":dates,
              "mature_labels":len(labeled),"minimum_dates":settings["minimum_dates"],
              "minimum_labels":settings["minimum_labels"],"target":"Next 7-day displayed sold-counter increment"}
    if dates < settings["minimum_dates"] or len(labeled) < settings["minimum_labels"]:
        return report
    splits = split_mature(frame)
    if splits is None or min(len(f) for f in splits) < 20:
        return {**report,"reason":"insufficient_labels_after_purge"}
    train, val, test = splits
    prep = lambda: ColumnTransformer([
        ("numeric",Pipeline([("impute",SimpleImputer(strategy="median",keep_empty_features=True)),
                              ("scale",StandardScaler())]),NUMERIC),
        ("category",OneHotEncoder(handle_unknown="ignore",sparse_output=False),CATEGORICAL)])
    models = {
        "recent_mean":None,
        "ridge":Pipeline([("prep",prep()),("model",Ridge(alpha=10))]),
        "gradient_boosting":Pipeline([("prep",prep()),("model",HistGradientBoostingRegressor(
            max_iter=100,max_leaf_nodes=15,l2_regularization=1,random_state=settings["seed"]))]),
    }
    validation, predictions = {}, {}
    for name, model in models.items():
        if model is not None:
            model.fit(train[NUMERIC+CATEGORICAL],train.target)
        pred = val.increment7.to_numpy() if model is None else np.maximum(0,model.predict(val[NUMERIC+CATEGORICAL]))
        validation[name] = float(mean_absolute_error(val.target,pred))
    selected = min(validation, key=validation.get)  # No access to test metrics during selection.
    for name, model in models.items():
        pred = test.increment7.to_numpy() if model is None else np.maximum(0,model.predict(test[NUMERIC+CATEGORICAL]))
        predictions[name] = {"mae":float(mean_absolute_error(test.target,pred)),
                             "rmse":float(np.sqrt(mean_squared_error(test.target,pred)))}
    selected_model = models[selected]
    latest = frame[frame.day == frame.day.max()].dropna(subset=["increment7"])
    future_values = np.array([]) if latest.empty else latest.increment7.to_numpy() if selected_model is None else np.maximum(0,selected_model.predict(latest[NUMERIC+CATEGORICAL]))
    forecasts = [{"country":r.country,"niche":r.niche,
        "product_ref":hashlib.sha256((r.country+r.product_id).encode()).hexdigest()[:10],
        "forecast_from":str(r.day.date()),"forecast_to":str((r.day+pd.Timedelta(days=7)).date()),
        "counter_increment":round(float(v),2)} for r,v in zip(latest.itertuples(),future_values)]
    def span(data):
        return {"rows":len(data),"first_date":str(data.day.min().date()),"last_date":str(data.day.max().date()),
                "last_label_end":str(data.target_end.max().date())}
    return {**report,"state":"evaluated","selected_model":selected,"validation_mae":validation,
        "test_metrics":predictions,"split":{"train":span(train),"validation":span(val),"test":span(test)},
        "dataset_sha256":hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        "seed":settings["seed"],"forecasts":forecasts,
        "interpretation":"Model selected only on validation. Test errors may be worse than the baseline; all results retained.",
        "evaluation_policy":"Rolling evaluation snapshot, not a repeatedly untouched holdout. No claim of real orders or profit."}
