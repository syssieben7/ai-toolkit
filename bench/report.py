#!/usr/bin/env python3
"""Aggregate results/*.json -> report.md + report.json + a self-contained reports/index.html
(inline CSS/SVG, no deps, opens offline). All in-repo; no external/VPS coupling.

The HTML has three parts:
  - Model comparison (latest run): pass% / avg tok-s / avg wall-s / cost as SVG bars.
  - Per-case grid: pass + tok/s per model x case.
  - History: trend of pass% and avg wall-s across past runs (results batched by time gap).
"""
import json, pathlib, time, html
ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT/"results"

# ---- load every result (full history), and the latest snapshot per (model,case) ----
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
(RESULTS).mkdir(exist_ok=True)
(RESULTS/"report.md").write_text(report_md)
(RESULTS/"report.json").write_text(json.dumps(
    {"generated": int(time.time()), "summary": summary, "cases": cases}, indent=2))

# ---- history: cluster all runs into batches by a >180s gap between sorted timestamps ----
def batches():
    ts_sorted = sorted({r["ts"] for r in all_rows})
    if not ts_sorted:
        return []
    groups, cur = [], [ts_sorted[0]]
    for t in ts_sorted[1:]:
        if t - cur[-1] > 180:
            groups.append(cur); cur = [t]
        else:
            cur.append(t)
    groups.append(cur)
    out = []
    for g in groups:
        gs = set(g)
        rs = [r for r in all_rows if r["ts"] in gs]
        per = {m: agg([r for r in rs if r["model"] == m]) for m in sorted({r["model"] for r in rs})}
        out.append((min(g), per))
    return out
HIST = batches()

# ---- tiny inline-SVG helpers ----
PALETTE = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#a855f7", "#06b6d4", "#ec4899"]
def color(m): return PALETTE[models.index(m) % len(PALETTE)] if m in models else "#888"

def svg_bars(title, items, unit=""):
    # items: [(label, value, color)]
    vals = [v for _, v, _ in items if v is not None]
    mx = max(vals) if vals else 1
    mx = mx or 1
    rh, gap, w = 26, 8, 360
    h = len(items)*(rh+gap)+10
    parts = [f'<div class="chart"><h3>{html.escape(title)}</h3>',
             f'<svg width="640" height="{h}" role="img">']
    for i, (label, v, c) in enumerate(items):
        y = i*(rh+gap)+5
        bw = int((v or 0)/mx*w)
        parts.append(f'<text x="0" y="{y+rh-8}" class="lbl">{html.escape(label)}</text>')
        parts.append(f'<rect x="150" y="{y}" width="{bw}" height="{rh}" rx="4" fill="{c}"/>')
        disp = "—" if v is None else (f"{v}{unit}")
        parts.append(f'<text x="{150+bw+6}" y="{y+rh-8}" class="val">{disp}</text>')
    parts.append('</svg></div>')
    return "".join(parts)

def svg_lines(title, series, xlabels, unit=""):
    # series: {model: [y or None,...]}; xlabels: [str,...]
    W, H, padl, padb, padt = 600, 220, 44, 28, 14
    flat = [y for ys in series.values() for y in ys if y is not None]
    mx = max(flat) if flat else 1
    mx = mx or 1
    n = max(len(xlabels), 1)
    def X(i): return padl + (0 if n == 1 else i*(W-padl-10)/(n-1))
    def Y(v): return padt + (1-(v/mx))*(H-padt-padb)
    parts = [f'<div class="chart"><h3>{html.escape(title)}</h3>',
             f'<svg width="{W}" height="{H}" role="img">']
    # axes
    parts.append(f'<line x1="{padl}" y1="{padt}" x2="{padl}" y2="{H-padb}" class="axis"/>')
    parts.append(f'<line x1="{padl}" y1="{H-padb}" x2="{W-6}" y2="{H-padb}" class="axis"/>')
    parts.append(f'<text x="0" y="{padt+4}" class="tick">{mx:g}{unit}</text>')
    parts.append(f'<text x="0" y="{H-padb}" class="tick">0</text>')
    for i, xl in enumerate(xlabels):
        parts.append(f'<text x="{X(i):.0f}" y="{H-padb+16}" class="tick" text-anchor="middle">{html.escape(xl)}</text>')
    for m, ys in series.items():
        pts = [(X(i), Y(v)) for i, v in enumerate(ys) if v is not None]
        if not pts: continue
        c = color(m)
        if len(pts) > 1:
            d = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            parts.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="2"/>')
        for x, y in pts:
            parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3" fill="{c}"/>')
    parts.append('</svg></div>')
    return "".join(parts)

def legend():
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{color(m)}"></i>{html.escape(m)}</span>' for m in models) + '</div>'

# ---- compose HTML ----
gen = time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())
by_q = sorted(summary, key=lambda x: -(x["pass_rate"] or -1))
grid_head = "".join(f"<th>{html.escape(c)}</th>" for c in cases)
grid_rows = ""
for m in models:
    tds = ""
    for c in cases:
        r = latest.get((m, c))
        if not r:
            tds += '<td class="na">—</td>'; continue
        ok = r.get("passed")
        cls = "ok" if ok else ("bad" if ok is False else "na")
        mark = "✓" if ok else ("✗" if ok is False else "·")
        tds += f'<td class="{cls}">{mark} <small>{r["tok_s"]}t/s · {r["wall_s"]}s</small></td>'
    grid_rows += f"<tr><th>{html.escape(m)}</th>{tds}</tr>"

xl = [time.strftime('%m-%d %H:%M', time.gmtime(ts)) for ts, _ in HIST]
hist_pass = {m: [per.get(m, {}).get("pass_rate") for _, per in HIST] for m in models}
hist_wall = {m: [per.get(m, {}).get("avg_wall") for _, per in HIST] for m in models}

html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ai-toolkit · model benchmark</title>
<style>
:root{{color-scheme:light dark}}
body{{font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px;max-width:1100px;margin:auto;
  background:#0b0f17;color:#e5e7eb}}
h1{{margin:0 0 2px}} h2{{margin:32px 0 8px;border-bottom:1px solid #283042;padding-bottom:4px}}
h3{{margin:0 0 6px;font-size:13px;color:#9ca3af;font-weight:600}}
.sub{{color:#9ca3af;margin:0 0 8px}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}}
.chart{{background:#111827;border:1px solid #283042;border-radius:10px;padding:12px}}
.lbl{{fill:#cbd5e1;font-size:12px}} .val{{fill:#e5e7eb;font-size:12px;font-weight:600}}
.axis{{stroke:#374151;stroke-width:1}} .tick{{fill:#6b7280;font-size:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px;background:#111827;border-radius:10px;overflow:hidden}}
th,td{{padding:7px 10px;text-align:left;border-bottom:1px solid #1f2937}}
td small{{color:#9ca3af}}
td.ok{{background:rgba(34,197,94,.12)}} td.bad{{background:rgba(239,68,68,.15)}} td.na{{color:#6b7280}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0;color:#cbd5e1;font-size:12px}}
.legend i{{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:middle}}
.podium{{font-size:13px;color:#cbd5e1;margin:6px 0 0}}
</style></head><body>
<h1>ai-toolkit · model benchmark</h1>
<p class="sub">generated {gen} · {len(models)} models × {len(cases)} cases · {len(HIST)} run(s) in history</p>
{legend()}

<h2>Model comparison (latest run)</h2>
<p class="podium">Ranked by quality, then wall-time. Note: high tok/s ≠ fast — watch <b>avg wall</b> (tokens generated × speed).</p>
<div class="grid2">
{svg_bars("Quality — pass %", [(s["model"], s["pass_rate"], color(s["model"])) for s in by_q], "%")}
{svg_bars("Speed — avg tok/s", [(s["model"], s["avg_tok_s"], color(s["model"])) for s in summary], "")}
{svg_bars("Latency — avg wall (s, lower=better)", [(s["model"], s["avg_wall"], color(s["model"])) for s in summary], "s")}
{svg_bars("Cost — total $", [(s["model"], s["cost"], color(s["model"])) for s in summary], "$")}
</div>

<h2>Per-case results</h2>
<table><tr><th>model</th>{grid_head}</tr>{grid_rows}</table>

<h2>History</h2>
{"<p class='sub'>Run the matrix again to build a trend — only one run so far.</p>" if len(HIST) < 2 else ""}
<div class="grid2">
{svg_lines("Quality over time (pass %)", hist_pass, xl, "%")}
{svg_lines("Latency over time (avg wall s)", hist_wall, xl, "s")}
</div>
</body></html>"""

(ROOT/"reports").mkdir(exist_ok=True)
(ROOT/"reports"/"index.html").write_text(html_doc)
print(report_md)
print(f"\n→ reports/index.html written ({len(models)} models, {len(cases)} cases, {len(HIST)} run(s))")
