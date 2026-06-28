# AGENTS.md — ai-toolkit

A model/backend **switcher** + reproducible **benchmark**. `models.yaml` is the single source of truth.

## Ground rules
- Never hardcode secrets; read keys from env (`key_env` in models.yaml). `.env` is gitignored.
- **Mac-Mini model management is via the Ollama HTTP API only** (`/api/pull`, `/api/delete`) — never local CLI (multi-user host, admin-only installs).
- Keep `models.yaml` the source of truth; everything generates from it. Don't duplicate model lists.
- temperature:0 + pinned refs for reproducibility. Record provenance on every result.

## Working MVP (already runs)
- `switch.py opencode <model>` writes `.opencode/opencode.json` + launch cmd.
- `bench/run.py`/`matrix.py`/`report.py` benchmark ollama + openai-type backends; report = quality% + tok/s + wall + $.
- 6 cases: code_i2c, code_bugfix, reason_logic, reason_math, agentic_ota, extract_json.

## TODO (build these out)
1. **Anthropic backend** in `run.py` (messages API; map usage→tokens; price→cost).
2. **switch.py: VSCode** (Continue/Cline `settings.json`) and **Claude-Code** (`.claude/settings.json`) generators.
3. **Better graders** beyond regex: compile/unit-test for code cases (write to /tmp, `cc -c`, run); optional **LLM-judge** (rubric scored by a frontier model) for open-ended cases.
4. **Cost/resource**: add `price_per_mtok` per cloud model; for local, optionally sample Mac GPU/power (asitop/mactop) and host CPU/mem during a run.
5. **Reproducibility**: pin model **digests**; run each case **N times**, report mean±stdev; record hardware + thermal state.
6. **Backend-path matrix**: same model via ollama-direct vs litellm vs openrouter — they differ (latency/quant/limits). Add a `paths:` axis.
7. **Tool/agent macro-bench** (separate from model micro-bench): a fixed mini-repo task ("implement feature, make tests pass") run via OpenCode/Claude-Code/VSCode-agent; measure **pass@1 + wall + $ + tokens** over N runs.
8. **Dashboard section**: `report.py` already writes `~/monitoring/reports/bench-latest.json`; add a "Model Benchmarks" section to the VPS `monitoring/generate-dashboard.sh` rendering it.
9. **Domain cases**: add real node-fleet/firmware/automation tasks as eval cases.

## Style
Small, focused changes. One logical change per commit. Match existing structure. Ask before destructive ops.
