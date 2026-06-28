#!/usr/bin/env python3
"""switch <tool> <model-id> — generate that tool's config from models.yaml + print launch cmd."""
import sys, json, pathlib, argparse, yaml
ROOT=pathlib.Path(__file__).resolve().parent
C=yaml.safe_load(open(ROOT/"models.yaml"))
def model(mid): return next(x for x in C["models"] if x["id"]==mid)
def opencode(m,b):
    prov="ollama" if b["type"]=="ollama" else m["backend"]
    base=b["base"].rstrip("/"); base=base if base.endswith("/v1") or b["type"]=="ollama" else base
    url=(base+"/v1") if b["type"]=="ollama" else base
    return {"$schema":"https://opencode.ai/config.json",
            "provider":{prov:{"npm":"@ai-sdk/openai-compatible","options":{"baseURL":url},
                              "models":{m["ref"]:{"name":m["id"]}}}},
            "permission":{"bash":{"*":"ask","ls*":"allow","cat*":"allow","grep*":"allow","find*":"allow",
                                   "git status*":"allow","git diff*":"allow","git add*":"allow","git commit*":"allow","git push*":"ask"}}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("tool"); ap.add_argument("model"); a=ap.parse_args()
    m=model(a.model); b=C["backends"][m["backend"]]
    if a.tool=="opencode":
        p=pathlib.Path(".opencode"); p.mkdir(exist_ok=True)
        (p/"opencode.json").write_text(json.dumps(opencode(m,b),indent=2))
        prov="ollama" if b["type"]=="ollama" else m["backend"]
        print(f"✓ .opencode/opencode.json → {a.model} ({m['ref']} @ {m['backend']})")
        print(f"  launch: opencode -m {prov}/{m['ref']}")
    else:
        print(f"tool '{a.tool}' not yet implemented — see AGENTS.md TODO (vscode/Continue, claude-code).")
if __name__=="__main__": main()
