# EVA - Evolutionary Verified Alignment harness

Pure standard-library Python; no dependencies for AST-only mode.

- phase1_symbolic_evolution.py - core loop demo (verifier, anti-gaming, calibration, novelty archive)
- phase2_code_evolution.py - code-task benchmark with unit-test splits, sandbox whitelist, hardcode detection, canary self-test, LLM hook (MOONSHOT_API_KEY)

Design doc: docs/EVA_alignment_training_design.md
Run: python3 eva/phase2_code_evolution.py --task all --gens 150 --out eva/results
CI:  .github/workflows/evolution_runner.yml runs on push and commits results to eva/results/
