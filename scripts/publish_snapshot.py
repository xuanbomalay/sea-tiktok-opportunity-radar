"""Publish only generated public outputs, atomically, using a scoped token."""
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def main():
    p=argparse.ArgumentParser();p.add_argument("directory");p.add_argument("--repository",default="xuanbomalay/sea-tiktok-opportunity-radar")
    a=p.parse_args();root=Path(a.directory)
    token=os.environ.get("RADAR_PUBLISH_TOKEN")
    if not token:
        raise SystemExit("RADAR_PUBLISH_TOKEN missing; site remains unchanged")
    if not (root/"data/latest.json").exists():
        raise SystemExit("No validated public snapshot")
    snapshot=json.loads((root/"data/latest.json").read_text(encoding="utf-8"))
    if snapshot.get("synthetic"):
        raise SystemExit("Refusing synthetic output as the production snapshot")
    def api(path,body=None,method=None):
        request=Request("https://api.github.com/repos/"+a.repository+path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method or ("POST" if body is not None else "GET"),
            headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","User-Agent":"SEA-Radar/0.1"})
        try:
            with urlopen(request,timeout=60) as response:
                raw=response.read()
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            error.radar_operation=f"GitHub {request.method} {path}"
            raise
    try:
        old=api("/git/ref/heads/gh-pages")["object"]["sha"]
    except HTTPError as e:
        if e.code != 404: raise SystemExit("Cannot read public deployment ref") from None
        old=None
    entries=[]
    for file in sorted(root.rglob("*")):
        if not file.is_file():continue
        rel=file.relative_to(root).as_posix()
        if not (rel in {"index.html",".nojekyll","demo/index.html","demo/.nojekyll"} or rel.startswith(("assets/","charts/","data/","demo/assets/","demo/charts/","demo/data/"))):
            raise SystemExit("Unexpected public output path")
        blob=api("/git/blobs",{"content":base64.b64encode(file.read_bytes()).decode(),"encoding":"base64"})
        entries.append({"path":rel,"mode":"100644","type":"blob","sha":blob["sha"]})
    tree=api("/git/trees",{"tree":entries})
    commit=api("/git/commits",{"message":"Publish validated daily research snapshot","tree":tree["sha"],"parents":[old] if old else []})
    if old:
        api("/git/refs/heads/gh-pages",{"sha":commit["sha"],"force":False},method="PATCH")
    else:
        api("/git/refs",{"ref":"refs/heads/gh-pages","sha":commit["sha"]})
    api("/dispatches",{"event_type":"snapshot-ready"})
    print("Published validated snapshot:",commit["sha"])


if __name__ == "__main__":
    try:main()
    except HTTPError as e:raise SystemExit(f"{getattr(e,'radar_operation','GitHub publication')} HTTP {e.code}; credentials omitted") from None
