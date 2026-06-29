#!/usr/bin/env python3
"""Aggregate results/*.json -> report.md + report.json + a self-contained reports/index.html.

In-repo only (no VPS coupling). The HTML is one file, inline CSS + vanilla JS (no CDN), and has:
  - Model comparison bars (quality / tok-s / wall / cost) with the per-metric winner highlighted.
  - A quality-vs-latency scatter (find the sweet-spot model).
  - Per-case grid (green pass / red fail) with grade details on hover.
  - Interactive FILTERS: toggle models and cases to focus any comparison.
  - HISTORY: pass%/wall trend lines + a "scan" dropdown to replay any past run's grid.
History is also persisted to reports/history.jsonl so it survives clearing results/.
"""
import json, pathlib, time, html
ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT/"results"
REPORTS = ROOT/"reports"

all_rows = [json.loads(p.read_text()) for p in RESULTS.glob("*.json")
            if p.name not in ("report.json",)]
latest = {}
for r in all_rows:
    k = (r["model"], r["case"])
    if k not in latest or r["ts"] > latest[k]["ts"]:
        latest[k] = r
rows = list(latest.values())
models = sorted({r["model"] for r in rows})
cases = sorted({r["case"] for r in rows})

def agg(rs):
    p = [r for r in rs if r.get("passed") is not None]
    return dict(n=len(rs),
        pass_rate=round(100*sum(1 for r in p if r["passed"])/len(p)) if p else None,
        avg_tok_s=round(sum(r["tok_s"] for r in rs)/len(rs), 1) if rs else 0,
        avg_wall=round(sum(r["wall_s"] for r in rs)/len(rs), 1) if rs else 0,
        cost=round(sum(r.get("cost_usd", 0) for r in rs), 4))
summary = [dict(model=m, **agg([r for r in rows if r["model"] == m])) for m in models]

# winners per metric (max pass/tok_s, min wall; min cost among >0 else 0)
def winner(key, mode):
    vals = [(s["model"], s[key]) for s in summary if s[key] is not None]
    if mode == "min_pos":
        vals = [(m, v) for m, v in vals if v > 0] or vals
    if not vals: return None
    return (min if mode.startswith("min") else max)(vals, key=lambda t: t[1])[0]
wins = {"pass_rate": winner("pass_rate", "max"), "avg_tok_s": winner("avg_tok_s", "max"),
        "avg_wall": winner("avg_wall", "min"), "cost": winner("cost", "min_pos")}

# ---- markdown (kept) ----
md = ["# AI model benchmark", f"_generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}_", "",
      "| model | quality (pass%) | avg tok/s | avg wall s | cost $ |", "|---|---|---|---|---|"]
for s in sorted(summary, key=lambda x: -(x["pass_rate"] or -1)):
    md.append(f"| {s['model']} | {s['pass_rate']}% | {s['avg_tok_s']} | {s['avg_wall']} | {s['cost']} |")
md += ["", "## per-case  (pass · tok/s)", "| model | "+" | ".join(cases)+" |", "|"+"---|"*(len(cases)+1)]
for m in models:
    cells = [(str(latest[(m,c)].get("passed"))[:1]+"·"+str(latest[(m,c)]["tok_s"])) if (m,c) in latest else "—"
             for c in cases]
    md.append(f"| {m} | "+" | ".join(cells)+" |")
report_md = "\n".join(md)
RESULTS.mkdir(exist_ok=True)
(RESULTS/"report.md").write_text(report_md)
(RESULTS/"report.json").write_text(json.dumps(
    {"generated": int(time.time()), "summary": summary, "cases": cases, "wins": wins}, indent=2))

# ---- history: cluster runs by >180s gap; keep full per-(model,case) grid per batch ----
def batches():
    ts_sorted = sorted({r["ts"] for r in all_rows})
    if not ts_sorted: return []
    groups, cur = [], [ts_sorted[0]]
    for t in ts_sorted[1:]:
        if t - cur[-1] > 180: groups.append(cur); cur = [t]
        else: cur.append(t)
    groups.append(cur)
    out = []
    for g in groups:
        gs = set(g); rs = [r for r in all_rows if r["ts"] in gs]
        bmodels = sorted({r["model"] for r in rs})
        per = {m: agg([r for r in rs if r["model"] == m]) for m in bmodels}
        grid = {f'{r["model"]}|{r["case"]}': {"passed": r.get("passed"), "tok_s": r["tok_s"],
                "wall_s": r["wall_s"], "detail": r.get("grade_detail", "")} for r in rs}
        out.append({"ts": min(g), "label": time.strftime('%m-%d %H:%M', time.gmtime(min(g))),
                    "per": per, "grid": grid, "cases": sorted({r["case"] for r in rs})})
    return out
HIST = batches()

# persist history rollup (survives `rm results/*.json`)
REPORTS.mkdir(exist_ok=True)
(REPORTS/"history.jsonl").write_text("\n".join(json.dumps(
    {"ts": b["ts"], "label": b["label"], "per": b["per"]}) for b in HIST))

# data blob for the JS (filters, scatter, historic scan)
DATA = {"models": models, "cases": cases, "summary": summary, "wins": wins,
        "latest": {f"{m}|{c}": ({"passed": latest[(m,c)].get("passed"), "tok_s": latest[(m,c)]["tok_s"],
                    "wall_s": latest[(m,c)]["wall_s"], "detail": latest[(m,c)].get("grade_detail","")}
                    if (m,c) in latest else None) for m in models for c in cases},
        "history": HIST}

PALETTE = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#a855f7", "#06b6d4", "#ec4899", "#84cc16"]
def color(m): return PALETTE[models.index(m) % len(PALETTE)] if m in models else "#888"

def svg_bars(title, key, unit, win_model):
    items = [(s["model"], s[key]) for s in summary]
    mx = max([v for _, v in items if v is not None] + [1]) or 1
    rh, gap, x0, barw = 24, 8, 140, 330
    h = len(items)*(rh+gap)+8
    p = [f'<div class="chart"><h3>{html.escape(title)}</h3>',
         f'<svg viewBox="0 0 600 {h}" width="100%" height="{h}" role="img">']
    for i, (m, v) in enumerate(items):
        y = i*(rh+gap)+4
        bw = int((v or 0)/mx*barw)
        star = ' ★' if m == win_model else ''
        p.append(f'<g data-model="{html.escape(m)}">')
        p.append(f'<text x="0" y="{y+rh-7}" class="lbl">{html.escape(m)}{star}</text>')
        p.append(f'<rect x="{x0}" y="{y}" width="{bw}" height="{rh}" rx="4" fill="{color(m)}" '
                 f'opacity="{1.0 if m==win_model else 0.78}"/>')
        p.append(f'<text x="{x0+bw+6}" y="{y+rh-7}" class="val">{"—" if v is None else str(v)+unit}</text>')
        p.append('</g>')
    p.append('</svg></div>')
    return "".join(p)

def svg_scatter():
    # x = quality (pass%), y = latency (avg wall, inverted: lower=better=higher on chart)
    pts = [s for s in summary if s["pass_rate"] is not None]
    W, H, pad = 600, 260, 44
    walls = [s["avg_wall"] for s in pts] or [1]
    wmax = max(walls + [1]) or 1
    def X(q): return pad + (q/100)*(W-pad-12)
    def Y(w): return pad + (w/wmax)*(H-pad-28)   # higher wall -> lower on chart
    p = [f'<div class="chart"><h3>Quality vs latency — top-left is best (high quality, low wait)</h3>',
         f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img">',
         f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-28}" class="axis"/>',
         f'<line x1="{pad}" y1="{H-28}" x2="{W-6}" y2="{H-28}" class="axis"/>',
         f'<text x="6" y="{pad+4}" class="tick">fast</text>',
         f'<text x="6" y="{H-30}" class="tick">slow {wmax:g}s</text>',
         f'<text x="{W-70}" y="{H-12}" class="tick">quality →</text>']
    for s in pts:
        m = s["model"]; x = X(s["pass_rate"]); y = Y(s["avg_wall"])
        p.append(f'<g data-model="{html.escape(m)}">'
                 f'<circle cx="{x:.0f}" cy="{y:.0f}" r="6" fill="{color(m)}"/>'
                 f'<text x="{x+9:.0f}" y="{y+4:.0f}" class="lbl">{html.escape(m)}</text></g>')
    p.append('</svg></div>')
    return "".join(p)

def svg_lines(title, metric, unit):
    series = {m: [b["per"].get(m, {}).get(metric) for b in HIST] for m in models}
    xl = [b["label"] for b in HIST]
    W, H, padl, padb, padt = 600, 220, 44, 28, 14
    flat = [y for ys in series.values() for y in ys if y is not None]
    mx = max(flat + [1]) or 1
    n = max(len(xl), 1)
    def X(i): return padl + (0 if n == 1 else i*(W-padl-10)/(n-1))
    def Y(v): return padt + (1-(v/mx))*(H-padt-padb)
    p = [f'<div class="chart"><h3>{html.escape(title)}</h3>',
         f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img">',
         f'<line x1="{padl}" y1="{padt}" x2="{padl}" y2="{H-padb}" class="axis"/>',
         f'<line x1="{padl}" y1="{H-padb}" x2="{W-6}" y2="{H-padb}" class="axis"/>',
         f'<text x="0" y="{padt+4}" class="tick">{mx:g}{unit}</text><text x="0" y="{H-padb}" class="tick">0</text>']
    for i, x in enumerate(xl):
        if i % max(1, n//6) == 0 or i == n-1:
            p.append(f'<text x="{X(i):.0f}" y="{H-padb+15}" class="tick" text-anchor="middle">{html.escape(x)}</text>')
    for m, ys in series.items():
        pts = [(X(i), Y(v)) for i, v in enumerate(ys) if v is not None]
        if not pts: continue
        p.append(f'<g data-model="{html.escape(m)}">')
        if len(pts) > 1:
            p.append(f'<polyline points="{" ".join(f"{x:.0f},{y:.0f}" for x,y in pts)}" '
                     f'fill="none" stroke="{color(m)}" stroke-width="2"/>')
        for x, y in pts: p.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3" fill="{color(m)}"/>')
        p.append('</g>')
    p.append('</svg></div>')
    return "".join(p)

# filters
mfilter = '<div class="filter"><b>models:</b>' + "".join(
    f'<label><input type="checkbox" class="mf" value="{html.escape(m)}" checked onchange="applyModel()">'
    f'<i style="background:{color(m)}"></i>{html.escape(m)}</label>' for m in models) + '</div>'
cfilter = '<div class="filter"><b>cases:</b>' + "".join(
    f'<label><input type="checkbox" class="cf" value="{html.escape(c)}" checked onchange="applyCase()">{html.escape(c)}</label>'
    for c in cases) + '</div>'

# per-case grid
ghead = "".join(f'<th data-case="{html.escape(c)}">{html.escape(c)}</th>' for c in cases)
gbody = ""
for m in models:
    tds = ""
    for c in cases:
        r = latest.get((m, c))
        if not r: tds += f'<td data-case="{html.escape(c)}" class="na">—</td>'; continue
        ok = r.get("passed"); cls = "ok" if ok else ("bad" if ok is False else "na")
        mark = "✓" if ok else ("✗" if ok is False else "·")
        tip = html.escape(str(r.get("grade_detail", "")))
        tds += (f'<td data-case="{html.escape(c)}" class="{cls}" title="{tip}">{mark} '
                f'<small>{r["tok_s"]}t/s · {r["wall_s"]}s</small></td>')
    gbody += f'<tr data-model="{html.escape(m)}"><th>{html.escape(m)}</th>{tds}</tr>'

runopts = "".join(f'<option value="{i}">{html.escape(b["label"])} ({len(b["cases"])} cases)</option>'
                  for i, b in enumerate(HIST))

CSS = """
:root{color-scheme:dark}
*{box-sizing:border-box}
body{font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px;max-width:1180px;margin:auto;background:#0b0f17;color:#e5e7eb}
h1{margin:0 0 2px}h2{margin:30px 0 8px;border-bottom:1px solid #283042;padding-bottom:4px}
h3{margin:0 0 6px;font-size:12.5px;color:#9ca3af;font-weight:600}
.sub{color:#9ca3af;margin:0 0 10px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
.chart{background:#111827;border:1px solid #283042;border-radius:10px;padding:12px;min-width:0}
.lbl{fill:#cbd5e1;font-size:12px}.val{fill:#e5e7eb;font-size:12px;font-weight:600}
.axis{stroke:#374151;stroke-width:1}.tick{fill:#6b7280;font-size:10px}
table{border-collapse:collapse;width:100%;font-size:13px;background:#111827;border-radius:10px;overflow:hidden}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid #1f2937;white-space:nowrap}
td small{color:#9ca3af}
td.ok{background:rgba(34,197,94,.12)}td.bad{background:rgba(239,68,68,.16)}td.na{color:#6b7280}
.filter{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:8px 0;color:#cbd5e1;font-size:12px;
  background:#0e1421;border:1px solid #283042;border-radius:8px;padding:8px 10px}
.filter label{display:inline-flex;align-items:center;gap:4px;cursor:pointer}
.filter i{display:inline-block;width:11px;height:11px;border-radius:2px}
.filter b{color:#9ca3af;margin-right:2px}
select{background:#111827;color:#e5e7eb;border:1px solid #283042;border-radius:6px;padding:4px 8px}
.scroll{overflow-x:auto}
"""

JS = """
function applyModel(){
  var on={}; document.querySelectorAll('.mf').forEach(function(c){on[c.value]=c.checked;});
  document.querySelectorAll('[data-model]').forEach(function(el){
    el.style.display = on[el.getAttribute('data-model')]===false ? 'none':'';});
}
function applyCase(){
  var on={}; document.querySelectorAll('.cf').forEach(function(c){on[c.value]=c.checked;});
  document.querySelectorAll('[data-case]').forEach(function(el){
    el.style.display = on[el.getAttribute('data-case')]===false ? 'none':'';});
}
var DATA=JSON.parse(document.getElementById('benchdata').textContent);
function scanRun(){
  var i=+document.getElementById('runsel').value, b=DATA.history[i];
  var cs=b.cases, h='<tr><th>model</th>'+cs.map(function(c){return '<th>'+c+'</th>';}).join('')+'</tr>';
  var ms={}; Object.keys(b.grid).forEach(function(k){ms[k.split('|')[0]]=1;});
  Object.keys(ms).sort().forEach(function(m){
    h+='<tr><th>'+m+'</th>'+cs.map(function(c){
      var r=b.grid[m+'|'+c]; if(!r) return '<td class="na">—</td>';
      var ok=r.passed, cls=ok?'ok':(ok===false?'bad':'na'), mk=ok?'✓':(ok===false?'✗':'·');
      return '<td class="'+cls+'" title="'+(r.detail||'')+'">'+mk+' <small>'+r.tok_s+'t/s · '+r.wall_s+'s</small></td>';
    }).join('')+'</tr>';
  });
  document.getElementById('scangrid').innerHTML=h;
}
window.addEventListener('DOMContentLoaded',function(){ if(DATA.history.length) scanRun(); });
"""

gen = time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())
parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ai-toolkit · model benchmark</title><style>{CSS}</style></head><body>
<h1>ai-toolkit · model benchmark</h1>
<p class="sub">generated {gen} · {len(models)} models × {len(cases)} cases · {len(HIST)} run(s) in history</p>
{mfilter}
<h2>Model comparison (latest run)</h2>
<p class="sub">★ = winner per metric. high tok/s ≠ fast — watch <b>avg wall</b>.</p>
<div class="grid2">
{svg_bars("Quality — pass %", "pass_rate", "%", wins["pass_rate"])}
{svg_bars("Speed — avg tok/s", "avg_tok_s", "", wins["avg_tok_s"])}
{svg_bars("Latency — avg wall (s, lower=better)", "avg_wall", "s", wins["avg_wall"])}
{svg_bars("Cost — total $", "cost", "$", wins["cost"])}
</div>
<h2>Sweet spot</h2>
<div class="grid2">{svg_scatter()}</div>
<h2>Per-case results (latest)</h2>
{cfilter}
<div class="scroll"><table><tr><th>model</th>{ghead}</tr>{gbody}</table></div>
<h2>History</h2>
<div class="grid2">
{svg_lines("Quality over time (pass %)", "pass_rate", "%")}
{svg_lines("Latency over time (avg wall s)", "avg_wall", "s")}
</div>
<h3 style="margin-top:14px">Scan a past run</h3>
<p class="sub">Replay any recorded run's per-case grid.</p>
<select id="runsel" onchange="scanRun()">{runopts}</select>
<div class="scroll" style="margin-top:8px"><table id="scangrid"></table></div>
<script id="benchdata" type="application/json">{json.dumps(DATA)}</script>
<script>{JS}</script>
</body></html>"""]

(REPORTS/"index.html").write_text("".join(parts))
print(report_md)
print(f"\n→ reports/index.html ({len(models)} models, {len(cases)} cases, {len(HIST)} runs) + reports/history.jsonl")
