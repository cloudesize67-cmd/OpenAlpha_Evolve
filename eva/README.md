# EVA - Evolutionary Verified Alignment harness

Pure standard-library Python; no dependencies for AST-only mode.

- phase1_symbolic_evolution.py - core loop demo (verifier, anti-gaming, calibration, novelty archive)
- phase2_code_evolution.py - code-task benchmark with unit-test splits, sandbox whitelist, hardcode detection, canary self-test, LLM hook (MOONSHOT_API_KEY)
- test_verifier_hardening.py - exploit regression suite (see "Hardening" below)

Design doc: docs/EVA_alignment_training_design.md
Run: python3 eva/phase2_code_evolution.py --task all --gens 150 --out eva/results
Test: python3 eva/test_verifier_hardening.py
CI:  .github/workflows/evolution_runner.yml runs on push and commits results to eva/results/

## Hardening: findings from the first committed run

Running the harness end-to-end surfaced two real behavioral patterns the
design doc's threat model (Section 6) predicts but the original verifier
didn't fully catch, plus one genuine search-capability gap. Confirmed by
executing the candidates directly, not by inspection:

1. **Memorization exploit (sum_to_n)** — the evolved "best" was
   `min(n, 6) ** 2`. It uses `n`, so the old hardcode check passed it, but it
   is wrong for ~98% of a wide integer range — a textbook P1 reward-hacking
   pattern the tiny fixed train/val/heldout splits alone couldn't expose.
2. **Bloated-but-correct formula (is_even)** — the evolved "best" was a
   convoluted boolean-arithmetic expression. Direct execution across 2000
   integers confirms it's actually correct everywhere — this is *not* a
   correctness exploit, but the kind of needless complexity a parsimony
   pressure should suppress in favor of simpler equivalents like `n % 2 == 0`.
3. **Search blind spot (collatz_step, sum_to_n)** — pure AST mutation
   plateaus well below solving these under a no-LLM budget. This is a
   generator-capability gap, not a verification-integrity problem; the fix
   that matters here is reporting it honestly rather than forcing false
   convergence.

### What changed in response

- **Probe split** (`CodeVerifier._make_probe_split` / `probe_report`): a wide
  synthetic input sample, generated with its own seeded RNG, used only to
  gate harvest eligibility — never fed into `adjusted_fitness`, so the search
  itself can't overfit to it. This is what catches pattern (1).
- **Occam's-razor tiebreak** (`selection_key`): fitness first, complexity
  (AST node count) second. Suppresses pattern (2) without needing to
  special-case it — any future bloated-but-correct candidate loses to a
  simpler correct rival automatically.
- **`verified_for_harvest` gate**: reports now explicitly separate candidates
  that converged and generalize (held-out *and* probe both ≥ 0.999) from
  ones that are merely the best a stalled search produced. Unconverged tasks
  are labeled `UNCONVERGED — do not harvest` in `summary.json` and the
  generated `_solution.py` header, so a downstream SFT/RLVR harvesting step
  (design doc L2) can never silently ingest a diagnostic artifact as ground
  truth. This directly addresses pattern (3): honest reporting over forced
  success.
- **Stall-triggered diversity injection**: when the population plateaus for
  20 generations, a fraction of the next generation is fresh
  `random_branch_expr` structures (forced `if/else`) instead of only mutating
  around the current elites. This measurably helps escape local optima (e.g.
  unblocked `clamp_0_100` from a `max(0, n)` plateau) but does not fully
  close the gap on `sum_to_n`/`collatz_step` without more generations or the
  LLM hook — consistent with the design doc's own Phase 2→3 roadmap.
- **Canary now covers the probe split too** (`self_test`), so evaluator
  drift on the anti-memorization gate itself is caught before every run.
- `eva/test_verifier_hardening.py` codifies both discovered patterns as
  permanent regression tests (design doc L6: "every discovered
  specification-gaming incident becomes a regression test").
