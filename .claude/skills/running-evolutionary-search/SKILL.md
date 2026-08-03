---
name: running-evolutionary-search
description: Runs OpenAlpha_Evolve's evolutionary search and reports results — either the LLM-driven main.py pipeline against a task YAML (e.g. examples/torsion_filter, examples/quantum_gravity_scaling_v2.yaml) or the dependency-free EVA harness (eva/phase2_code_evolution.py). Use when asked to run/evolve/search for a program, filter, or champion, or when main.py, EVA, evaluator.py, task config.yaml, or a fitness/combined_score ladder is mentioned.
---

# Running evolutionary search

This repo has two independent search paths. Pick based on what's being evolved.

## Path A — LLM-driven pipeline (`main.py`)

Used for the curated tasks under `examples/*.yaml` (e.g. `torsion_filter/config.yaml`,
`quantum_gravity_scaling_v2.yaml`). Mutations come from an LLM via litellm
(`config/settings.py` reads `LLM_SECONDARY_MODEL`/`LLM_PRIMARY_MODEL`, default
`gemini/...`).

**Check for a key before running** — litellm needs a provider key as a real env var
(`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.):

```bash
env | grep -iE "GEMINI|OPENAI|ANTHROPIC_API|GOOGLE_API"
```

If nothing is set, stop and tell the user to add the key via their environment's
settings (not by pasting it into chat — chat history isn't a secret store). No
`.env` file is required for the key itself; litellm reads it straight from the
process environment.

Once a key is present:

```bash
python main.py examples/torsion_filter/config.yaml
```

This runs the full generation loop (`POPULATION_SIZE` × `GENERATIONS`, see
`config/settings.py`) and can take a while and burn real API spend — mention that
before running if it's not obvious from context. Report the final best program(s),
their `fitness_scores`, and code from the log output.

## Path B — EVA harness (no LLM required)

`eva/phase2_code_evolution.py` is pure standard-library Python (symbolic/AST
mutation), with an optional LLM hook via `MOONSHOT_API_KEY` that isn't required.
Use this when no LLM key is available, or when the task is one of EVA's canned
problems (`double_plus_one`, `sum_to_n`, `is_even`, `collatz_step`, `clamp_0_100`).

```bash
python3 eva/phase2_code_evolution.py --task all --gens 150 --out eva/results
```

Pass `--task <name>` to run a single task. Runs are seeded/deterministic — a rerun
with unchanged code reproduces `eva/results/summary.json` (check `git status`
after running; no diff means nothing new to commit). CI
(`.github/workflows/evolution_runner.yml`) already runs this on every push
touching `**.py` and commits results back to `eva/results/`.

## Scoring reference for the external evaluators

Both curated tasks score candidates *outside* the test suite (tests are smoke-only,
so the answer isn't leaked):

```bash
python examples/torsion_filter/evaluator.py --selftest              # sanity: baseline >> naive MA
python examples/torsion_filter/evaluator.py --heldout <program.py>  # gate: combined_score > 0

python physics_verification/grid_evaluator.py --selftest
python physics_verification/grid_evaluator.py <program.py> --heldout
```

`combined_score` is always *relative to an engineered baseline* — positive beats
it. A champion only counts as publishable if it's positive on `--heldout`, not
just the training seeds/grid.

## Reporting results

Give a compact table (task, train score or pass-rate, held-out, solved y/n) — don't
paste full per-generation logs. Call out anything that plateaued below baseline or
failed to generalize to held-out data.
