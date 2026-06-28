# ai-toolkit — model/backend switcher + reproducible benchmark

One **source of truth** (`models.yaml`) drives both:
- **switch.py** — generate a tool's config (OpenCode now; VSCode/Claude-Code TODO) for any model/backend and print the launch command.
- **bench/** — reproducible benchmark: **quality (pass/score) + speed (tok/s, wall) + cost ($)** across models × cases, with results fed into the VPS monitoring dashboard.

## Quickstart
```bash
pip install -r requirements.txt
cp .env.example .env && $EDITOR .env      # cloud keys (local Ollama needs none)
set -a; . ./.env; set +a

# switch OpenCode to a model:
python switch.py opencode mac-coder-mlx

# benchmark:
python bench/run.py --model qwen3-coder --case code_i2c     # one
python bench/matrix.py --tag code                            # all code-tagged models × all cases
#   → results/*.json, results/report.md, results/report.json
#   → (on the VPS) ~/monitoring/reports/bench-latest.json for the dashboard
```

## Layout
- `models.yaml` — backends (ollama/litellm/openrouter/anthropic) + models + default params + tags
- `switch.py` — config switcher
- `bench/run.py` — single run (quality+speed+cost+provenance)
- `bench/matrix.py` — full matrix → report
- `bench/report.py` — aggregate → md/json table + dashboard feed
- `cases/<name>.md` (prompt) + `cases/<name>.check` (regex grader)
- `results/` — timestamped outputs (gitignored)

## Hand to OpenCode
Open this repo in OpenCode and point it at `AGENTS.md` — it lists exactly what to extend
(VSCode/Claude-Code config gen, Anthropic backend, LLM-judge/compile graders, cost prices,
multi-run variance, tool-level agent benchmarks, dashboard section). The MVP already runs.
