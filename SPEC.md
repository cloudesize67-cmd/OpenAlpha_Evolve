# SPEC.md — OpenAlpha_Evolve $0 Evolution Engine Completion (2026-08-24)

Single source of truth for this build. Implement faithfully. No unilateral
interface changes. THE LAW (from PROJECT_STATE.md) governs everything:
deterministic evaluators only; held-out numbers only ever published; seeds /
evaluator code / reference implementations NEVER appear in LLM prompts;
actor never judges itself.

Target environment: Android Termux, Python 3, numpy available, NO pip-heavy
deps. Everything below is **stdlib + numpy only**. No litellm, no openai
package, no requests — `urllib` only.

---

## Module 1 — `examples/free_engine.py` (NEW, shared $0 LLM router)

Stdlib-only fallback chain across free OpenAI-compatible chat endpoints.

### Public interface (SACRED — both evolution loops import exactly this)

```python
class EngineDownError(RuntimeError): ...

def complete(prompt: str, system: str = "", temperature: float = 0.7,
             max_tokens: int = 2048) -> tuple[str, str]:
    """Try providers in chain order. Returns (text, provider_name).
    Raises EngineDownError when every configured provider fails."""

def report() -> str:
    """Human-readable provider status table (calls/failures/status)."""

def configured_providers() -> list[str]:
    """Names of providers that have a key (or need none) right now."""
```

### Provider chain (default order; override via env FREE_ROUTER_ORDER="a,b,c")

| name      | endpoint (POST, OpenAI chat-completions schema)                              | model                        | env key           |
|-----------|-------------------------------------------------------------------------------|------------------------------|-------------------|
| groq      | https://api.groq.com/openai/v1/chat/completions                              | llama-3.3-70b-versatile      | GROQ_API_KEY      |
| gemini    | https://generativelanguage.googleapis.com/v1beta/openai/chat/completions     | gemini-2.5-flash             | GEMINI_API_KEY    |
| cerebras  | https://api.cerebras.ai/v1/chat/completions                                  | gpt-oss-120b                 | CEREBRAS_API_KEY  |
| openrouter| https://openrouter.ai/api/v1/chat/completions                                | qwen/qwen3-coder:free        | OPENROUTER_API_KEY|
| github    | https://models.github.ai/inference/chat/completions                          | openai/gpt-4o-mini           | GITHUB_TOKEN      |
| mistral   | https://api.mistral.ai/v1/chat/completions                                   | mistral-small-latest         | MISTRAL_API_KEY   |
| local     | $LOCAL_MODEL_URL/chat/completions (default http://127.0.0.1:8080/v1)         | local                        | none (key "none") |

Rules:
- Skip providers whose env key is unset (local never skipped by key rule).
- Auth: `Authorization: Bearer <key>`, JSON body
  `{"model":..., "messages":[{system?},{user}], "temperature":..., "max_tokens":...}`.
- On HTTP 429/5xx, auth error, or network error: retry same provider up to
  3 times with exponential backoff (5s→10s→20s), then BENCH it for 300 s
  (module-level cooldown dict) and fall through to the next provider.
- Track per-provider `{"calls": n, "failures": n}` and `last_provider_used`.
- 120 s per-request timeout.

### Mock mode (MANDATORY for offline verification)

If env `FREE_ENGINE_MOCK=1`: never touch the network. Return
`("```python\n" + <parent code extracted from the prompt's last python fence,
or a trivial valid pass-through if none> + "\n# mock mutation <counter>\n```", "mock")`.
A module-level counter makes each reply unique. This lets full evolution
loops run offline with real deterministic scoring.

### CLI

`python free_engine.py --selftest` → live probe ("Reply with exactly:
ROUTER_OK"), prints answering provider, verdict, and `report()` table.
Trust the probe, not marketing pages.

---

## Module 2 — `examples/torsion_filter/run_evolution.py` (REWIRE)

Keep the ENTIRE existing structure (preflight gate reproducing
naive 3.847 / baseline 5.956; SYSTEM_MSG + USER_TEMPLATE unchanged;
extract_block hygiene unchanged; population 16; 70/30 parent pick;
checkpoints; JSONL traces; final held-out instruction unchanged).

Changes ONLY:
1. Delete `call_gemini` and the `GEMINI_URL`/key-only logic.
2. Import the engine: `sys.path.insert(0, str(HERE.parent))` then
   `from free_engine import complete, report, EngineDownError`.
3. Each iteration calls `complete(prompt, system=SYSTEM_MSG)`; on
   `EngineDownError`, sleep 60 s and retry the SAME iteration (free tiers
   recover; never fake a result).
4. Trace records gain a `"provider"` field from the returned provider name
   (RLVR dataset needs to know which model made which candidate).
5. CLI: keep `--iterations`, `--preflight-only`. Replace `--model` with
   `--router-status` (prints `report()` and exits). Update the module
   docstring: engine is now the $0 fallback chain; any subset of keys works.
6. Preflight still runs BEFORE any key check and `--preflight-only` still
   works with zero keys set.

---

## Module 3 — `examples/noesis_coordination/run_evolution.py` (NEW, Milestone B loop)

Mirror Module 2's architecture against `evaluator.py` in the same dir.

### Candidate contract (from evaluator.py — already fixed, do not change)
Program defines `detect_campaign(posts) -> list[list[int]]` (aliases:
`detect`, `flag_coordinated`). posts = list of dicts
`{"account": int, "t": float, "tokens": tuple[int,...], "tags": tuple[int,...]}`.
Clusters = lists of account ids; clusters of size >= 2 count as flagged.

### Preflight gate (must reproduce sandbox-verified ladder, 2026-08-06)
In-process: import evaluator, run its detectors on TRAIN_SEEDS/TRAIN_KW:
- naive ≈ -0.147, engineer baseline ≈ 0.668, strong ≈ 1.489
  (tolerance ±0.15; ordering naive < baseline < strong must hold)
- Print held-out context line: baseline collapses to ≈ 0.0 on held-out
  difficulty (known ladder fact) — informational only.
- `--preflight-only` exits after the gate. FAIL → exit 1.

### Prompt (THE LAW — leak audit mandatory)
System + user text describes ONLY the general problem: detect clusters of
coordinated inauthentic accounts in a post stream; signals may include
near-duplicate content, synchronized posting times, and shared hashtag
signatures; organic decoys exist; robustness across worlds matters.
NEVER include: seed values, TRAIN/HELDOUT kwargs, generator code,
evaluator code, or the reference detectors' thresholds/weights.
User template shows current best candidate code + its score, asks for an
improved `detect_campaign`. Stdlib + numpy only; reply in one python fence.

### Extraction & hygiene
Same pattern as torsion: pull ```python fence; require one of the contract
function names; REJECT code containing: `open(`, `import os`, `import sys`,
`subprocess`, `socket`, `urllib`, `__import__`, `eval(`, `exec(`,
`import importlib`. Wrap into a program file; score via subprocess:
`python evaluator.py <tmp_candidate>` → last stdout line is a dict;
`combined_score` is fitness (candidate metric minus engineer-baseline
metric on train seeds). Timeout 120 s (pairwise signals are O(n²)).

### Loop
Identical policy to torsion: seed scored first (print actual; measured
2026-08-24 at ≈ -0.015 vs the engineer baseline — the shipped seed heuristic
is weak but not trivial), population
cap 16, parent 70% best / 30% better-half random, checkpoint
`checkpoints/population.json` every 10 iterations + at end, traces
`traces/run_<ts>.jsonl` with `provider` field, NEW BEST saves
`checkpoints/best_program.py`. Engine via Module 1; EngineDownError →
sleep 60 s, retry same iteration.

### End of run
Print best TRAIN combined_score, then exactly:
"The ONLY number you may publish is the held-out one. Run it yourself:"
`  python evaluator.py --heldout checkpoints/best_program.py`

---

## Verification (Stage 2 — done by verifier, all offline)

1. `FREE_ENGINE_MOCK=1 python examples/torsion_filter/run_evolution.py --preflight-only` → prints 3.847 / 5.956 / PASS.
2. `FREE_ENGINE_MOCK=1 python examples/torsion_filter/run_evolution.py --iterations 6` → completes; traces + checkpoint + best_program.py exist.
3. Same two gates for `examples/noesis_coordination/run_evolution.py` (ladder ordering gate; 6-iteration mock run completes).
4. `python examples/free_engine.py --selftest` with no keys → clean "chain down, set a key" message (no traceback).
5. Leak audit: grep prompt strings in both loops for "TRAIN_SEEDS", "HELDOUT", "engineer_baseline", "make_campaign", seed integers — must be absent from prompt text.

## Build record (2026-08-24)

Built by two parallel coder agents on git worktrees, merged by orchestrator,
then independently verified: **10/10 gates PASS, zero Law violations,
evaluator files untouched (git-diff empty).** Verdict: SHIP. Pushed to
main as commits 2cce079 (engine + torsion), 460b902 (noesis), plus docs.
