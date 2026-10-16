import json
from pathlib import Path
import shutil
import tempfile
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.offline import get_plotlyjs
from .config import ROOT
from .storage import atomic_json

PALETTE = {"MY":"#58d6bd","TH":"#80a9ff","VN":"#f6bd70"}


def figures(snapshot):
    theme = dict(template="plotly_dark",paper_bgcolor="#111b2a",plot_bgcolor="#111b2a",
        font=dict(family="Arial, sans-serif",color="#dce6f1",size=13),
        margin=dict(l=65,r=30,t=80,b=65),height=510)
    bubble = go.Figure()
    valid = [g for g in snapshot["groups"] if g["growth7"] is not None and g["competition_proxy"] is not None]
    for country,color in PALETTE.items():
        rows = [g for g in valid if g["country"] == country]
        if rows:
            bubble.add_trace(go.Scatter(x=[g["competition_proxy"] for g in rows],y=[g["growth7"]*100 for g in rows],
                mode="markers+text",text=[g["label"] for g in rows],textposition="top center",name=country,
                marker=dict(color=color,size=[14+min(35,g["sample_products"]*2) for g in rows],opacity=.8)))
    bubble.update_layout(**theme,title="Sample opportunity map / matched 7-day growth",xaxis_title="Observed sellers / sampled listings (proxy)",yaxis_title="Matched counter growth (%)")
    if not valid:
        bubble.update_xaxes(visible=False)
        bubble.update_yaxes(visible=False)
        bubble.add_annotation(text="Collecting matched history · no opportunity points yet",xref="paper",yref="paper",x=.5,y=.5,showarrow=False,font=dict(size=18))
    labels = list(dict.fromkeys(g["label"] for g in snapshot["groups"]))
    matrix = [[next((g["sample_products"] for g in snapshot["groups"] if g["country"]==c and g["label"]==label),0) for c in PALETTE] for label in labels]
    heat = go.Figure(go.Heatmap(z=matrix,x=list(PALETTE),y=labels,colorscale=[[0,"#1b2d41"],[1,"#58d6bd"]],text=matrix,texttemplate="%{text}",colorbar=dict(title="Products")))
    heat.update_layout(**theme,title="Observed sample coverage / not market size")
    trend = go.Figure()
    for country,color in PALETTE.items():
        rows = [r for r in snapshot["trends"] if r["country"] == country]
        for niche in dict.fromkeys(r["niche"] for r in rows):
            selected = [r for r in rows if r["niche"]==niche]
            trend.add_trace(go.Scatter(x=[r["date"] for r in selected],y=[r["median_sold_count"] for r in selected],
                mode="lines+markers",name=f"{country} / {niche}",line=dict(color=color),connectgaps=False))
    trend.update_layout(**theme,title="Median public sold counter / changing search samples",xaxis_title="Observation date (UTC)",yaxis_title="Displayed cumulative counter (not daily sales)")
    if not snapshot["trends"]:
        trend.add_annotation(text="Waiting for the first real collection",xref="paper",yref="paper",x=.5,y=.5,showarrow=False,font=dict(size=18))
    if snapshot["synthetic"]:
        for fig in (bubble,heat,trend):
            fig.add_annotation(text="SYNTHETIC DEMO — NOT MARKET EVIDENCE",xref="paper",yref="paper",x=.5,y=1.12,showarrow=False,font=dict(color="#f6bd70",size=13))
    return {"opportunity":bubble,"coverage":heat,"trends":trend}


def validate_public(snapshot):
    json.dumps(snapshot,allow_nan=False)
    text = json.dumps(snapshot)
    for forbidden in ("Authorization", "apify_api_", "AIza", "source_run_id", "raw_sha256", "seller_id"):
        if forbidden in text:
            raise ValueError("Public export contains a private/secret field")
    if snapshot["synthetic"] and snapshot["data_mode"] != "synthetic_demo":
        raise ValueError("Synthetic output must be visibly labeled")


def build_site(snapshot, brief, output, *, export_images=True):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    validate_public(snapshot)
    share_assets = output.name == "demo" and (output.parent/"assets"/"plotly.min.js").exists()
    with tempfile.TemporaryDirectory(prefix="radar-build-",dir=output.parent) as tmp:
        stage = Path(tmp)
        shutil.copytree(ROOT/"web",stage,dirs_exist_ok=True,ignore=shutil.ignore_patterns("assets") if share_assets else None)
        if share_assets:
            html = (stage/"index.html").read_text(encoding="utf-8").replace('"assets/','"../assets/')
            (stage/"index.html").write_text(html,encoding="utf-8")
        else:
            (stage/"assets").mkdir(exist_ok=True)
            (stage/"assets"/"plotly.min.js").write_text(get_plotlyjs(),encoding="utf-8")
        atomic_json(stage/"data"/"latest.json",snapshot)
        (stage/"data"/"report.md").write_text(brief,encoding="utf-8")
        pd.DataFrame(snapshot["groups"]).to_csv(stage/"data"/"summary.csv",index=False)
        if export_images:
            (stage/"charts").mkdir(exist_ok=True)
            charts = figures(snapshot)
            pio.write_images(fig=list(charts.values()),file=[str(stage/"charts"/(name+".png")) for name in charts],width=1400,height=650,scale=1)
        # Publishing receives a complete validated directory, never a half-written dataset.
        # Locally replace individual files only after all rendering has succeeded.
        output.mkdir(exist_ok=True)
        for file in stage.rglob("*"):
            if file.is_file():
                dest = output/file.relative_to(stage)
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,dest)
    return output
