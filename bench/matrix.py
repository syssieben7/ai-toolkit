#!/usr/bin/env python3
"""Run all (or filtered) models x all cases, then build the report."""
import subprocess, sys, pathlib, yaml, argparse
ROOT=pathlib.Path(__file__).resolve().parent.parent
c=yaml.safe_load(open(ROOT/"models.yaml"))
ap=argparse.ArgumentParser(); ap.add_argument("--tag"); ap.add_argument("--models"); a=ap.parse_args()
models=[m["id"] for m in c["models"]]
if a.models: models=a.models.split(",")
elif a.tag: models=[m["id"] for m in c["models"] if a.tag in m.get("tags",[])]
cases=sorted(p.stem for p in (ROOT/"cases").glob("*.md"))
for mid in models:
    for case in cases:
        try: subprocess.run([sys.executable, str(ROOT/"bench"/"run.py"),"--model",mid,"--case",case], check=False)
        except Exception as e: print(f"  {mid}/{case} ERROR {e}")
subprocess.run([sys.executable, str(ROOT/"bench"/"report.py")])
