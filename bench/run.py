#!/usr/bin/env python3
"""Run cases x models. Captures QUALITY (pass/score) + SPEED (tok/s, wall) + COST ($) + provenance."""
import sys, json, time, os, argparse, urllib.request, re, pathlib
import yaml
import graders  # bench/ is sys.path[0] when run as `python bench/run.py`
ROOT = pathlib.Path(__file__).resolve().parent.parent
def cfg(): return yaml.safe_load(open(ROOT/"models.yaml"))
def _post(url, payload, headers=None, timeout=600):
    req=urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json",**(headers or {})})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read()), time.time()-t0
def call(c, mid, prompt):
    m=next((x for x in c["models"] if x["id"]==mid), None)
    if m is None:
        raise SystemExit(f"model '{mid}' not in models.yaml. Available: "
                         + ", ".join(x["id"] for x in c["models"]))
    b=c["backends"][m["backend"]]
    p=m.get("params",{}); ref=m["ref"]
    if b["type"]=="ollama":
        payload={"model":ref,"prompt":prompt,"stream":False,
                 "options":{"temperature":p.get("temperature",0),"num_predict":p.get("num_predict",1024)}}
        if "think" in p: payload["think"]=p["think"]
        body,wall=_post(b["base"].rstrip("/")+"/api/generate", payload)
        text=body.get("response","") or ""; toks=body.get("eval_count",0)
        dur=(body.get("eval_duration") or 0)/1e9
        tps=round(toks/dur,1) if dur else 0
    elif b["type"]=="openai":
        key=os.environ.get(b.get("key_env",""),"")
        payload={"model":ref,"messages":[{"role":"user","content":prompt}],
                 "temperature":p.get("temperature",0),"max_tokens":p.get("num_predict",1024)}
        body,wall=_post(b["base"].rstrip("/")+"/chat/completions", payload, {"Authorization":f"Bearer {key}"})
        text=body["choices"][0]["message"]["content"] or ""
        toks=body.get("usage",{}).get("completion_tokens",0); tps=round(toks/wall,1) if wall else 0
    else:
        raise SystemExit(f"backend type {b['type']} not implemented yet (see AGENTS.md)")
    cost=round(toks/1e6*m.get("price_per_mtok",0),6)
    return dict(text=text, tokens=toks, tok_s=tps, wall_s=round(wall,1), cost_usd=cost,
                backend=m["backend"], ref=ref, params=p)
def grade(name, text):
    """Prefer cases/<name>.test (JSON: exec_py|match_answer|parse_json);
    fall back to legacy cases/<name>.check regex. Returns {pass,details} or None."""
    tf=ROOT/"cases"/(name+".test")
    if tf.exists():
        spec=json.loads(tf.read_text()); gt=spec.get("grader")
        if gt=="exec_py":      return graders.exec_py(text, spec.get("tests",[]), spec.get("entry"))
        if gt=="match_answer": return graders.match_answer(text, spec.get("expected"))
        if gt=="parse_json":   return graders.parse_json(text, spec.get("required",[]))
        return {"pass": None, "details": f"unknown grader: {gt}"}
    chk=ROOT/"cases"/(name+".check")
    if chk.exists():
        return {"pass": bool(re.search(chk.read_text().strip(), text, re.I|re.S)), "details": "regex"}
    return None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",required=True); ap.add_argument("--case",required=True)
    a=ap.parse_args(); c=cfg()
    prompt=(ROOT/"cases"/(a.case+".md")).read_text()
    r=call(c, a.model, prompt)
    gr=grade(a.case, r["text"])
    r.update(model=a.model, case=a.case, ts=int(time.time()),
             passed=(gr or {}).get("pass"), grade_detail=(gr or {}).get("details"))
    (ROOT/"results").mkdir(exist_ok=True)
    (ROOT/"results"/f"{r['ts']}_{a.model}_{a.case}.json").write_text(json.dumps(r,indent=2))
    print(f"{a.model:16} {a.case:14} pass={str(r['passed']):5} {r['tok_s']:>6} t/s  {r['wall_s']:>6}s  ${r['cost_usd']}  {r.get('grade_detail','')}")
if __name__=="__main__": main()
