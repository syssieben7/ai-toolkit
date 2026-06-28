#!/usr/bin/env python3
import json, pathlib, time, os
ROOT=pathlib.Path(__file__).resolve().parent.parent
rows=[json.loads(p.read_text()) for p in (ROOT/"results").glob("*.json") if p.name not in ("report.json",)]
latest={}
for r in rows:
    k=(r["model"],r["case"])
    if k not in latest or r["ts"]>latest[k]["ts"]: latest[k]=r
rows=list(latest.values())
models=sorted({r["model"] for r in rows}); cases=sorted({r["case"] for r in rows})
def agg(m):
    rs=[r for r in rows if r["model"]==m]; p=[r for r in rs if r.get("passed") is not None]
    return dict(model=m, n=len(rs),
        pass_rate=round(100*sum(1 for r in p if r["passed"])/len(p)) if p else None,
        avg_tok_s=round(sum(r["tok_s"] for r in rs)/len(rs),1) if rs else 0,
        avg_wall=round(sum(r["wall_s"] for r in rs)/len(rs),1) if rs else 0,
        cost=round(sum(r.get("cost_usd",0) for r in rs),4))
summary=[agg(m) for m in models]
md=["# AI model benchmark", f"_generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}_","",
    "| model | quality (pass%) | avg tok/s | avg wall s | cost $ |","|---|---|---|---|---|"]
for s in sorted(summary,key=lambda x:-(x["pass_rate"] or -1)):
    md.append(f"| {s['model']} | {s['pass_rate']}% | {s['avg_tok_s']} | {s['avg_wall']} | {s['cost']} |")
md+=["","## per-case  (pass · tok/s)","| model | "+" | ".join(cases)+" |","|"+"---|"*(len(cases)+1)]
for m in models:
    cells=[]
    for cs in cases:
        r=latest.get((m,cs))
        cells.append((str(r.get("passed"))[:1]+"·"+str(r["tok_s"])) if r else "—")
    md.append(f"| {m} | "+" | ".join(cells)+" |")
report_md="\n".join(md)
(ROOT/"results"/"report.md").write_text(report_md)
out={"generated":int(time.time()),"summary":summary,"cases":cases}
(ROOT/"results"/"report.json").write_text(json.dumps(out,indent=2))
dash=pathlib.Path(os.path.expanduser("~/monitoring/reports"))
if dash.is_dir():
    (dash/"bench-latest.json").write_text(json.dumps(out,indent=2)); print("→ ~/monitoring/reports/bench-latest.json written")
print(report_md)
