# OpenAlpha_Evolve — Agent Guide

This document is intended for AI coding agents (and human contributors) working on the OpenAlpha_Evolve codebase. It provides a high-level overview of the architecture, explains the responsibilities of each agent/module, and documents the conventions used across the repository.

---

## Project Overview

OpenAlpha_Evolve is a Python framework that autonomously evolves algorithmic solutions using Large Language Models (LLMs). It is inspired by research such as Google DeepMind's AlphaEvolve and applies an evolutionary loop to iteratively generate, evaluate, mutate, and select Python programs.

Key capabilities:

- LLM-driven code generation via LiteLLM (supports Gemini, OpenAI, Anthropic, and other providers).
- Evolutionary algorithm with mutation, bug-fix, and selection phases.
- Island model for parallel subpopulations with migration.
- Sandboxed code evaluation using Docker.
- Gradio web interface and YAML-based task definitions.

---

## Repository Layout

```text
./
├── code_generator/        # Generates and applies diffs to produce new programs.
├── database_agent/        # Persists programs and metadata (JSON-backed in-memory store).
├── evaluator_agent/       # Runs generated code in a Docker sandbox and scores fitness.
├── prompt_designer/       # Builds prompts for initial generation, mutation, and bug-fixing.
├── selection_controller/  # Selects parents and survivors; manages islands and migration.
├── task_manager/          # Orchestrates the full evolutionary cycle.
├── core/                  # Shared data structures and abstract interfaces.
├── config/                # Configuration loading and default settings.
├── examples/              # Example YAML task definitions.
├── tests/                 # Unit and integration tests.
├── app.py                 # Gradio web entry point.
├── main.py                # CLI entry point for YAML-based tasks.
├── requirements.txt       # Python dependencies.
├── .env.example           # Example environment variables.
└── README.md              # User-facing project documentation.
```

---

## Core Data Structures

Defined in `core/interfaces.py`:

- **`Program`**: Represents a single evolved solution.
  - `id`, `code`, `fitness_scores`, `generation`, `parent_id`, `island_id`, `errors`, `status`, `created_at`, `task_id`.
- **`TaskDefinition`**: Describes the problem to solve.
  - `id`, `description`, `function_name_to_evolve`, `input_output_examples`, `allowed_imports`, `tests`, `evaluation_criteria`, `expert_knowledge`, etc.
- **`BaseAgent`**: Abstract base class that every agent extends.

---

## Agent Responsibilities

### `TaskManagerAgent` (`task_manager/agent.py`)

The central orchestrator. It:

1. Initializes the population by generating `POPULATION_SIZE` programs.
2. Evaluates each program.
3. For each generation:
   - Selects parents.
   - Generates offspring via mutation or bug-fix prompts.
   - Evaluates offspring.
   - Selects survivors to form the next generation.
4. Returns the best program(s) found.

### `PromptDesignerAgent` (`prompt_designer/agent.py`)

Builds LLM prompts:

- `design_initial_prompt()` — asks for a complete implementation of `function_name_to_evolve`.
- `design_mutation_prompt()` — asks for targeted improvements as diff blocks.
- `design_bug_fix_prompt()` — asks for fixes to specific errors as diff blocks.

Diffs must follow the format:

```text
<<<<<<< SEARCH
exact original lines
=======
replacement lines
>>>>>>> REPLACE
```

### `CodeGeneratorAgent` (`code_generator/agent.py`)

Calls the configured LLM and returns generated code. Supports:

- Raw code generation.
- Diff generation and application against a parent program.
- Model selection via `settings.LLM_PRIMARY_MODEL` / `settings.LLM_SECONDARY_MODEL`.

### `EvaluatorAgent` (`evaluator_agent/agent.py`)

Validates and scores programs:

- Syntax check.
- Execution inside a Docker container (`code-evaluator:latest` by default).
- Fitness scoring:
  - `correctness`: fraction of passing tests.
  - `passed_tests` / `total_tests`.
  - `runtime_ms`: average runtime.
- Supports both direct `output` comparison and custom `validation_func` checks.

### `InMemoryDatabaseAgent` (`database_agent/agent.py`)

Stores `Program` instances in memory and persists them to `program_database.json`. Provides retrieval by ID, generation, task, and best-by-objective.

### `SelectionControllerAgent` (`selection_controller/agent.py`)

Implements the evolutionary selection strategy:

- `select_parents()` — chooses promising programs for reproduction.
- `select_survivors()` — combines current population and offspring into the next generation.
- `initialize_islands()` / migration — divides the population across islands and periodically exchanges programs.

---

## Configuration

Configuration lives in `config/settings.py` and can be overridden via environment variables (loaded from `.env`).

Important settings:

| Setting | Description |
|--------|-------------|
| `LITELLM_DEFAULT_MODEL` | Default model string passed to LiteLLM. |
| `LLM_PRIMARY_MODEL` | Model used for high-fitness mutation and bug-fixing. |
| `LLM_SECONDARY_MODEL` | Model used for initial generation and lower-fitness mutation. |
| `POPULATION_SIZE` | Number of programs per generation. |
| `GENERATIONS` | Total number of generations to run. |
| `NUM_ISLANDS` | Number of islands in the island model. |
| `MIGRATION_INTERVAL` / `MIGRATION_RATE` | Migration frequency and proportion. |
| `DOCKER_IMAGE_NAME` | Docker image used by the evaluator. |
| `EVALUATION_TIMEOUT_SECONDS` | Maximum runtime allowed per evaluation. |
| `DATABASE_PATH` | File used by the in-memory database. |
| `LOG_LEVEL` / `LOG_FILE` | Logging configuration. |

Environment variables are documented in `.env.example`.

---

## Running the Project

### CLI

```bash
python -m main examples/shortest_path.yaml
```

### Gradio Web UI

```bash
python app.py
```

The web UI will print a local URL (e.g., `http://127.0.0.1:7860`) and an optional public share link.

### Tests

```bash
pytest -v -s
```

The existing GitHub Actions workflow (`Run Unit Test via Pytest`) runs this command on every push.

---

## Defining a Task

Tasks are defined in YAML files. Example structure:

```yaml
task_id: "your_task_id"
task_description: |
  Detailed problem description, including expected function behavior and constraints.
function_name: "your_function_name"
allowed_imports: ["module1", "module2"]

tests:
  - description: "Test group description"
    name: "Test group name"
    test_cases:
      - input: [arg1, arg2]
        output: expected_output
      - input: [arg1, arg2]
        validation_func: |
          def validate(output_from_function):
              return isinstance(output_from_function, bool) and output_from_function is True
```

See `examples/shortest_path.yaml` for a complete example.

---

## Coding Conventions

- **Language**: Python 3.10+.
- **Async**: Agent execution methods are `async` where I/O or LLM calls are involved.
- **Logging**: Use `logging.getLogger(__name__)`; log levels are controlled by `settings.LOG_LEVEL`.
- **Dataclasses**: Core entities use `@dataclass` from `core/interfaces.py`.
- **Diff format**: Mutation and bug-fix prompts require SEARCH/REPLACE diff blocks. Code must not be returned as raw diff markers.
- **Docker**: The evaluator expects a built image named `code-evaluator:latest` by default. Build it from `evaluator_agent/Dockerfile`.
- **Environment secrets**: API keys are loaded from `.env`. Never commit secrets.

---

## Common Tasks for Agents

### Adding a New Agent

1. Create a new package directory (e.g., `my_agent/`).
2. Implement the agent class inheriting from the appropriate interface in `core/interfaces.py`.
3. Add unit tests under `tests/`.
4. Wire the agent into `TaskManagerAgent` if it participates in the evolutionary loop.

### Modifying the Evolutionary Loop

- Most loop logic lives in `TaskManagerAgent.manage_evolutionary_cycle()`.
- Selection behavior is controlled by `SelectionControllerAgent`.
- Fitness objectives and scoring are controlled by `EvaluatorAgent`.

### Changing LLM Behavior

- Adjust prompt templates in `prompt_designer/agent.py`.
- Adjust model selection logic in `task_manager/agent.py` and `config/settings.py`.
- LiteLLM model strings follow the format `provider/model-name`.

### Adding New Task Examples

Add YAML files under `examples/` and verify them with `python -m main examples/<your_example>.yaml`.

---

## Testing Notes

- Existing tests use `unittest` and `pytest`.
- Docker execution is mocked in tests; the evaluator agent tests patch `asyncio.create_subprocess_exec`.
- Run the full suite before submitting changes:

```bash
pytest -v -s
```

---

## Contribution Reminders

- Keep changes focused and minimal.
- Update this guide if you change architecture or conventions.
- Do not commit API keys or other secrets.
- Ensure tests pass and new behavior is covered by tests when possible.

---

*This file is a living document. Update it as the project evolves.*
