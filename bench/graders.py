#!/usr/bin/env python3
"""Deterministic graders for bench cases. Stdlib only, no compilation.

Three grader types, selected per-case via cases/<name>.test (JSON):
  exec_py      — actually RUN the model's Python and assert input->expected pairs
  match_answer — normalized / numeric-aware answer match (reason_/math cases)
  parse_json   — extract JSON, json.loads, assert required keys present

Each returns {"pass": bool, "details": str}.

exec_py runs the candidate via the same interpreter (sys.executable = the repo
.venv when run through .venv/bin/python) in a throwaway temp dir, under a hard
subprocess timeout so an infinite loop can't hang the bench. This is a CORRECTNESS
harness, not a security sandbox — it executes our own benchmark prompts, not
untrusted input. Don't point it at hostile code.
"""
import json, os, re, subprocess, sys, tempfile

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)
_DEF = re.compile(r"def\s+([A-Za-z_]\w*)\s*\(")


def _extract_code(text: str) -> str:
    m = _FENCE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()


def exec_py(text: str, tests: list, entry: str | None = None) -> dict:
    """Run the model's Python, call `entry`(input) per test, compare to expected.

    test item: {"input": {"n": 3}, "expected": 14}  -> called as entry(n=3)
               {"input": [1, 2],   "expected": 3 }  -> called as entry(1, 2)
    pass = the code runs, every call matches expected, exit 0.
    """
    code = _extract_code(text)
    fn = entry or (_DEF.search(code).group(1) if _DEF.search(code) else None)
    if not fn:
        return {"pass": False, "details": "no function definition found in output"}

    harness = (
        code
        + "\n\nimport json as _j, sys as _s\n"
        + "_cases = " + json.dumps(tests) + "\n"
        + "for _c in _cases:\n"
        + "    _inp, _exp = _c['input'], _c['expected']\n"
        + "    try:\n"
        + "        _got = " + fn + "(**_inp) if isinstance(_inp, dict) else " + fn + "(*_inp)\n"
        + "    except Exception as _e:\n"
        + "        print('FAIL ' + _j.dumps({'input': _inp, 'error': repr(_e)})); _s.exit(1)\n"
        + "    if _got != _exp:\n"
        + "        print('FAIL ' + _j.dumps({'input': _inp, 'expected': _exp, 'got': _got})); _s.exit(1)\n"
        + "print('OK')\n"
    )
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "candidate.py")
        with open(path, "w") as fh:
            fh.write(harness)
        try:
            p = subprocess.run([sys.executable, path], capture_output=True,
                               text=True, timeout=10, cwd=d)
        except subprocess.TimeoutExpired:
            return {"pass": False, "details": "timeout (>10s) — likely infinite loop"}
    out = (p.stdout or "").strip()
    ok = p.returncode == 0 and out.endswith("OK")
    if ok:
        return {"pass": True, "details": f"{len(tests)} tests passed"}
    detail = out or (p.stderr or "").strip().splitlines()[-1:] or ["no output"]
    if isinstance(detail, list):
        detail = detail[0]
    return {"pass": False, "details": detail[:300]}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def match_answer(text: str, expected) -> dict:
    """Numeric-aware if `expected` parses as a number (compare the LAST number in
    the output); otherwise case/space-insensitive substring match."""
    try:
        ev = float(expected)
        nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
        if nums and abs(float(nums[-1]) - ev) < 1e-9:
            return {"pass": True, "details": f"numeric match: {nums[-1]}"}
        return {"pass": False, "details": f"expected {expected}; last nums={nums[-3:]}"}
    except (ValueError, TypeError):
        ok = _norm(expected) in _norm(text)
        return {"pass": ok, "details": "substring match" if ok else f"'{expected}' not in output"}


def parse_json(text: str, required: list) -> dict:
    """Extract the first {...} object, json.loads it, assert required keys exist."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {"pass": False, "details": "no JSON object found"}
    try:
        obj = json.loads(m.group(0))
    except Exception as e:
        return {"pass": False, "details": f"json parse error: {e}"}
    if not isinstance(obj, dict):
        return {"pass": False, "details": "top-level JSON is not an object"}
    missing = [k for k in required if k not in obj]
    if missing:
        return {"pass": False, "details": f"missing keys: {missing}"}
    return {"pass": True, "details": f"valid json; {len(required)} required keys present"}
