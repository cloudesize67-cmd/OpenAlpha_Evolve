# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This repo contains **four largely independent projects** that happen to share a
checkout. Know which one you're touching before you start:

1. **OpenAlpha_Evolve** (repo root: `main.py`, `app.py`, and the `*_agent`/
   `*_controller`/`*_designer`/`*_manager` packages) — the primary project. An
   async, agent-based framework (inspired by DeepMind's AlphaEvolve) that uses
   an LLM via LiteLLM to iteratively generate, evaluate, and evolve Python
   functions against user-supplied test cases.
2. **`eva/`** — a separate, dependency-free "Evolutionary Verified Alignment"
   research harness (own README, own CI job). Not wired into the main
   evolutionary loop.
3. **`physics_verification/`** — a standalone computational audit (SymPy) of a
   physics dispute in the literature, with its own tests. Unrelated to code
   evolution; see `physics_verification/README.md` before touching it — it
   makes careful, narrow claims and any change to the checks should preserve
   that precision.
4. **`scripts/office/` + `scripts/merge_runs.py`** — a small, unrelated `.docx`
   (WordprocessingML) XML-editing toolkit. See `scripts/office/README.md`.

## Commands

### Core evolutionary framework
```bash
pip install -r requirements.txt
cp .env.example .env            # then fill in API keys / model config

# Run a task defined in YAML (see examples/*.yaml)
python -m main examples/shortest_path.yaml
python -m main examples/quantum_gravity_scaling.yaml

# Gradio web UI (interactive task definition + run)
python app.py

# Build the Docker sandbox image used to execute candidate programs
docker build -t code-evaluator:latest evaluator_agent/
```
Docker must be installed and running — `evaluator_agent/agent.py` shells out to
`docker run`/`docker stop`/`docker kill` to execute every candidate program in
an isolated, network-disabled container (`DOCKER_NETWORK_DISABLED`), so there
is no non-Docker fallback path.

### Tests
```bash
pytest -v -s                                    # everything (what CI runs)
python -m pytest physics_verification/           # physics audit only
python -m pytest tests/test_docx_pipeline.py     # docx pipeline only
python -m pytest tests/test_evaluator_agent.py::TestClassName::test_name  # single test
```
Async tests use stdlib `unittest.IsolatedAsyncioTestCase`, not `pytest-asyncio`
(not a dependency) — follow that pattern in `tests/test_evaluator_agent.py` /
`tests/test_corpus_seeding.py` when adding new async tests.

### `eva/` harness (separate from the above)
```bash
python3 eva/phase2_code_evolution.py --task all --gens 150 --out eva/results
```
Runs in CI via `.github/workflows/evolution_runner.yml` on every push touching
a `.py` file, and commits results back to `eva/results/`.

### Run archival
```bash
# After a run, snapshot program_database.json into a durable, committed form:
python scripts/archive_run.py --label pop12_gen8 --config "POPULATION_SIZE=12 GENERATIONS=8"
```
`program_database.json` at the repo root is overwritten in place on every run
and lives in an ephemeral container — it is not where results should be kept.
`scripts/archive_run.py` writes to `data/runs/<timestamp>[__label]/` (full
programs + lineage) and updates `data/best_corpus/<task_id>.jsonl` (deduped
best-per-task corpus). See `data/README.md`.

## Architecture (OpenAlpha_Evolve core)

### Agent pipeline and contracts
Every agent implements an `async execute(...)` method and a matching interface
defined in `core/interfaces.py` (`TaskManagerInterface`,
`PromptDesignerInterface`, `CodeGeneratorInterface`, `EvaluatorAgentInterface`,
`DatabaseAgentInterface`, `SelectionControllerInterface`, plus unused stubs
`RLFineTunerInterface`/`MonitoringAgentInterface`). `core/interfaces.py` is also
where the two central dataclasses live: `Program` (id, code, fitness_scores,
generation, parent_id, island_id, status, errors) and `TaskDefinition` (task
id, description, function_name_to_evolve, input_output_examples,
allowed_imports, tests, expert_knowledge, optional evolve-block markers for
whole-file evolution). Read this file first when working on any agent — it's
the contract every agent package (`code_generator/`, `database_agent/`,
`evaluator_agent/`, `prompt_designer/`, `selection_controller/`,
`task_manager/`) implements, each as a single `agent.py` beside an empty
`__init__.py`.

`TaskManagerAgent.manage_evolutionary_cycle()` (`task_manager/agent.py`) is the
orchestrator and owns the loop; the other five agents are its collaborators:

1. **`PromptDesignerAgent`** builds the initial/mutation/bug-fix prompts for a
   task (`prompt_designer/agent.py`). Mutation and bug-fix prompts ask the LLM
   for a **diff**, not a full rewrite.
2. **`CodeGeneratorAgent`** (`code_generator/agent.py`) calls the LLM via
   LiteLLM and, when a diff was requested, applies it to the parent code
   (`_apply_diff`).
3. **`EvaluatorAgent`** (`evaluator_agent/agent.py`) syntax-checks the code,
   then runs it inside a throwaway Docker container against
   `task.input_output_examples`, scoring correctness/runtime into
   `Program.fitness_scores`. `EVALUATION_TIMEOUT_SECONDS` bounds each run.
4. **`InMemoryDatabaseAgent`** (`database_agent/agent.py`) persists all
   programs to `program_database.json` (`DATABASE_PATH`) — despite the class
   name, it's file-backed, not purely in-memory.
5. **`SelectionControllerAgent`** (`selection_controller/agent.py`) implements
   an **island model**: `Island` subpopulations (`NUM_ISLANDS`) evolve mostly
   independently, with periodic migration (`_perform_migration`,
   `MIGRATION_INTERVAL`/`MIGRATION_RATE`) between them. It selects parents each
   generation and survivors for the next.

### Dual-model strategy
`task_manager/agent.py` deliberately uses two LLM "roles", not one model:
`LLM_SECONDARY_MODEL` ("Flash" — cheap/fast) drives the initial population and
mutations of low-fitness programs; `LLM_PRIMARY_MODEL` ("Pro" — stronger) takes
over once a parent's correctness crosses
`HIGH_FITNESS_THRESHOLD_FOR_PRIMARY_LLM` (default 0.8), and for bug-fixing.
Leaving both roles unset collapses everything to `LITELLM_DEFAULT_MODEL`. All
LLM auth is handled by LiteLLM's own provider-prefixed env vars (e.g. a model
string of `gemini/...` picks up `GEMINI_API_KEY` automatically) — there is no
separate per-role API key.

### Corpus seeding
`TaskManagerAgent._load_corpus_seeds` warm-starts generation 0 from
`data/best_corpus/<task_id>.jsonl` when present (`SEED_FROM_CORPUS`, default
on; capped by `SEED_CORPUS_COUNT` at `POPULATION_SIZE - 1` so fresh generation
always still happens). Tasks with no corpus file behave exactly as before.

### Task definitions
Tasks are normally defined as YAML in `examples/` (see
`README.md`'s "Defining Your Own Algorithmic Quests" section for the schema:
`task_id`, `task_description`, `function_name`, `allowed_imports`,
`expert_knowledge`, and `tests` → `test_cases` with either `output` or a
`validation_func`). `main.py`'s `load_task_from_yaml` parses this into a
`TaskDefinition`. Some example tasks (e.g. `examples/torsion_filter/`) are
larger, self-contained mini-projects with their own deterministic evaluator,
seed program, and config — read their local README before modifying.

### Configuration
All tunables live in `config/settings.py`, reading from `.env` via
`python-dotenv` (see `.env.example` for the full annotated list: LLM roles,
population/generation counts, island-model params, Docker settings, corpus
seeding, retry/timeout settings). Prefer adding new tunables here over hardcoding
in an agent.

## Conventions

- Every agent method that can be slow (LLM calls, code execution, DB I/O) is
  `async` and awaited; keep new agent methods async to match.
- Mutation/bug-fix prompts and their application are diff-based, not
  full-file replacement — preserve this when touching `PromptDesignerAgent` or
  `CodeGeneratorAgent._apply_diff`.
- `program_database.json` and `data/runs/`, `data/best_corpus/` are the only
  durable state; treat root-level `program_database.json` as scratch and
  `data/` as the place results should land (via `scripts/archive_run.py`).
