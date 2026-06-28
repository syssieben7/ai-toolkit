# ai-toolkit — model/backend switcher + reproducible benchmark

One **source of truth** (`models.yaml`) drives both:
- **switch.py** — generate a tool's config (OpenCode now; VSCode/Claude-Code TODO) for any model/backend and print the launch command.
- **bench/** — reproducible benchmark: **quality (pass/score) + speed (tok/s, wall) + cost ($)** across models × cases, with results fed into the VPS monitoring dashboard.

## Quickstart
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # repo-local, never global pip
cp .env.example .env && $EDITOR .env      # cloud keys (local Ollama needs none)
set -a; . ./.env; set +a

# switch OpenCode to a model:
.venv/bin/python switch.py opencode mac-coder-mlx

# benchmark:
.venv/bin/python bench/run.py --model qwen3-coder --case code_py_func   # one
.venv/bin/python bench/matrix.py --tag code                             # all code-tagged models × all cases
#   → results/*.json, results/report.md, results/report.json
#   → (on the VPS) ~/monitoring/reports/bench-latest.json for the dashboard
```

## Layout
- `models.yaml` — backends (ollama/litellm/openrouter/anthropic) + models + default params + tags
- `switch.py` — config switcher
- `bench/run.py` — single run (quality+speed+cost+provenance)
- `bench/matrix.py` — full matrix → report
- `bench/report.py` — aggregate → md/json table + dashboard feed
- `cases/<name>.md` (prompt) + `cases/<name>.test` (grader spec; legacy `.check` = regex fallback)
- `results/` — timestamped outputs (gitignored)

## Case graders (`cases/<name>.test`, JSON)
No compilation — all graders run with stdlib + the repo `.venv`. Pick one per case:
- **exec_py** — actually runs the model's Python and asserts input→expected:
  `{"grader":"exec_py","entry":"fn_name","tests":[{"input":{"n":3},"expected":14}]}`
  (`input` as a dict → `fn(**input)`, as a list → `fn(*input)`; `entry` optional, else first `def`).
  Hard 10s subprocess timeout; a crash/wrong answer/timeout = fail (with details).
- **match_answer** — `{"grader":"match_answer","expected":80}` — numeric-aware if `expected`
  is a number (matches the last number in the output), else case/space-insensitive substring.
- **parse_json** — `{"grader":"parse_json","required":["name","version","ports"]}` — extracts the
  first `{...}`, `json.loads`, asserts the keys exist.
- No `.test`? Falls back to `cases/<name>.check` regex. Grader logic lives in `bench/graders.py`.

## Hand to OpenCode
Open this repo in OpenCode and point it at `AGENTS.md` — it lists exactly what to extend
(VSCode/Claude-Code config gen, Anthropic backend, LLM-judge/compile graders, cost prices,
multi-run variance, tool-level agent benchmarks, dashboard section). The MVP already runs.
