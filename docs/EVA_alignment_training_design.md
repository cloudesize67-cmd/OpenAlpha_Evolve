# Evolutionary Verified Alignment (EVA)

**Design Document — v1.0 — 2026-08-02**
*An AlphaEvolve-inspired training process to replace subjective human-feedback alignment with verifiable, calibrated, tamper-resistant optimization.*

---

## 1. Executive Summary

Standard RLHF/DPO alignment trains models against **what humans prefer**, not **what is true**. This produces predictable behavioral pathologies: reward hacking via confident tone and verbosity, sycophancy, calibration degeneration, and hallucination as a rational optimization strategy.

This document specifies a layered training process whose core is an **AlphaEvolve-style evolutionary loop**: candidates are generated, scored by **deterministic verifiers** (not human annotators), and refined through population-based selection. Verified winners are harvested as ground-truth training data for SFT/RLVR. Human preference tuning is retained only for the genuinely subjective residue, hardened with noise-robust objectives (Dr. DPO / VAR). A calibration layer (DCPO-style) ensures expressed confidence tracks verifiable accuracy, and an evaluator-hardening layer defends against specification gaming.

A working prototype of the core loop ships with this document (`evolutionary_verifier_prototype.py`).

---

## 2. Problem Statement: Behavioral Failure Patterns

| # | Pattern | Source | Mechanism |
|---|---------|--------|-----------|
| P1 | **Reward hacking via style proxies** | Model | Confident tone, length, and formatting correlate with annotator upvotes; model optimizes surface features over correctness |
| P2 | **Hallucination as rational strategy** | Model | Under a preference reward, a fluent fabricated answer beats an honest "I don't know" |
| P3 | **Sycophancy** | Model | DPO/RLHF rewards agreement with the user's premise over correction |
| P4 | **Calibration degeneration** | Model | Preference loss + KL penalty collapse output entropy; model is overconfident on wrong answers |
| P5 | **Mode collapse / verbosity inflation** | Model | Single-policy gradient descent against a static reward model converges to one degenerate "long, safe, confident" style |
| P6 | **Annotator heuristics** | Human | Length bias, position bias, fatigue; contradictory labels treated as ground truth |
| P7 | **Corporate opacity → user cynicism** | Institution | Aesthetic tuning marketed as principled alignment; brittle behavior in production destroys trust |

**Root cause:** the reward signal is a *noisy subjective proxy* for correctness. Any sufficiently capable optimizer will exploit the proxy instead of the intent (Goodhart's law).

---

## 3. Design Principles

1. **Ground truth over preference.** Wherever correctness is computable, the reward must come from a deterministic verifier (compiler, proof checker, test suite, fact checker) — never a human ranking.
2. **Population search over single-trajectory descent.** Maintain diverse candidates; let weak ones die instead of being reinforced. This directly counters P5 and explores multiple solution strategies.
3. **Process over outcome.** Score intermediate reasoning steps (PRM), not just final answers, so correct answers via flawed reasoning are not rewarded.
4. **Calibrated confidence.** Overconfident errors must cost more than admitted uncertainty (counters P4).
5. **Assume the evaluator will be attacked.** Evolution is an excellent exploit-finder. Held-out tests, adversarial probes, and canary self-tests are first-class components, not afterthoughts.
6. **Quarantine the subjective.** Human preference data is used only where no verifier exists, and only through noise-robust objectives.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     EVA TRAINING PIPELINE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  L1 ┌─────────────── EVOLUTIONARY CORE (verifiable domains) ──────┐ │
│     │  Generator ──► Verifier Harness ──► Selection / Mutation    │ │
│     │  (LLM + AST      (deterministic      (tournament, elitism,  │ │
│     │   operators)      tests, canaries,    novelty archive)      │ │
│     │                   held-out splits)                          │ │
│     └──────────────────────┬──────────────────────────────────────┘ │
│                            ▼  verified winner traces                │
│  L2  SFT / RLVR on harvested ground-truth data                      │
│                            ▼                                        │
│  L3  Process-Supervised Reward Model (score reasoning steps)        │
│                            ▼                                        │
│  L4  Calibration Objective (DCPO-style overconfidence penalty)      │
│                            ▼                                        │
│  L5  Robust preference tuning (Dr. DPO / VAR) — subjective residue  │
│                            ▼                                        │
│  L6  Evaluator hardening: adversarial tests, held-out suites,       │
│      canary probes, exploit bounties  (feeds back into L1)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Module Specifications

### 5.1 L1 — Evolutionary Generator
- **Population:** N candidate programs/reasoning traces (prototype: N=50).
- **Proposal operators:** (a) LLM-driven mutation/crossover conditioned on task description + parent code (`llm_propose` hook); (b) AST-level structural mutations as a no-API fallback.
- **Diversity:** a novelty archive of structural fingerprints; previously unseen structures receive a small fitness bonus. Prevents the population from collapsing onto one shape (the evolutionary analog of mode collapse).

### 5.2 L1 — Verifier Harness
The trust anchor of the whole system. Deterministic, sandboxed, tamper-aware:

| Check | Purpose |
|-------|---------|
| Safe execution whitelist | No calls/attributes/imports; resource-limited eval |
| Time budget | Blocks pathological/DoS candidates |
| Hardcode detection | Large magic literals ⇒ memorizing outputs, not learning the function — halve fitness |
| Complexity cap + anti-bloat penalty | Prevents degenerate growth that games test coverage |
| Train / val / held-out splits | Selection sees train only; held-out used **exclusively** for final reporting — the classic defense against overfitting the visible tests |
| **Canary self-test** | A known reference solution must score near-perfect before every run; if it doesn't, the *evaluator* is broken or tampered with — abort |

### 5.3 L1 — Selection & Population Management
- Tournament selection (k=3) on **adjusted** fitness, elitism (top 4 survive intact), 25% crossover / 75% mutation mix.
- Early stop when a candidate is both near-perfect on train and generalizes to the validation split.

### 5.4 L2 — Data Harvesting → SFT / RLVR
Every verified winner (code + full verifier transcript + step trace) is written to a curated dataset. This is the critical shift from AlphaEvolve-as-search to AlphaEvolve-as-**training-data factory**: instead of paying annotators to imitate quality, the loop manufactures provably correct examples. RLVR then trains the policy with binary ground-truth rewards on this distribution.

### 5.5 L3 — Process Supervision (PRM)
A step-level reward model scores each intermediate reasoning step, not only the final answer. Correct answers reached via invalid steps are penalized — closing the loophole where fluent nonsense occasionally lands on the right result.

### 5.6 L4 — Calibration Objective (DCPO-style)
Each candidate's self-consistency on the train split is its *claimed* confidence; accuracy on the validation split is the *verified* confidence. Selection penalizes `λ · max(0, claimed − verified)` — an overconfidence tax. At the policy level, this maps to Decoupled Calibration and Policy Optimization: reasoning quality and expressed confidence are optimized as separate objectives so the model learns to say "uncertain" when it cannot verify.

### 5.7 L5 — Robust Preference Tuning (subjective residue only)
For open-ended, non-verifiable behavior (tone, helpfulness, safety judgment): Dr. DPO optimizes against worst-case pairwise label noise; VAR converts alignment into a stable offline reward-weighted SFT loss, removing fragile online sampling. Human noise is quarantined to the smallest possible surface.

### 5.8 L6 — Evaluator Hardening (continuous)
- Held-out test suites rotated and expanded from real failure reports.
- Adversarial test generation: a red-team model whose explicit job is to find inputs where current verifiers can be gamed.
- Exploit archive: every discovered specification-gaming incident becomes a regression test.

---

## 6. Threat Model: Anti-Gaming

| Attack | Layer | Mitigation |
|--------|-------|------------|
| Candidate memorizes test outputs | L1 | Hardcode detection, held-out splits, rotated tests |
| Candidate exploits verifier bug | L1/L6 | Canary self-test, exploit bounties, verifier redundancy |
| Population collapses to one degenerate strategy | L1 | Novelty archive, structural diversity bonus |
| Correct answer, wrong reasoning | L3 | Step-level PRM scoring |
| Overconfident wrong answers | L4 | DCPO calibration tax |
| Annotator label noise poisons policy | L5 | Dr. DPO worst-case pairwise robustness; VAR offline stability |
| Evaluator drift / silent corruption | L6 | Canary probes every run; versioned verifier audits |

---

## 7. Metrics & Acceptance Criteria

| Metric | Target |
|--------|--------|
| Held-out accuracy (verifiable tasks) | ≥ 99% of train accuracy (generalization gap ≈ 0) |
| Calibration gap (claimed − verified confidence) | ≤ 0.02 |
| Distinct structures explored per run | Monotonically increasing (no premature collapse) |
| % training data from verified sources | ≥ 80% for verifiable domains |
| Canary self-test pass rate | 100% (hard gate) |
| Known-exploit regression suite | 100% pass |

---

## 8. Roadmap

- **Phase 1 (done, this package):** Core loop + verifier harness prototype on symbolic regression; LLM hook interface defined.
- **Phase 2:** Plug an LLM into `llm_propose` (Kimi API or any OpenAI-compatible endpoint); move to a code-domain task with real unit tests (e.g., HumanEval-style).
- **Phase 3:** Harvest verified traces → RLVR fine-tune a small open model; add PRM step scoring.
- **Phase 4:** Calibration objective at policy level; robust preference layer for subjective residue; red-team harness.

---

## 9. Prototype Validation (actual run)

`evolutionary_verifier_prototype.py`, 120 generations, pop=50, seed=42:

- Evolved `x - 5 + (x * x + (x + x))` — exactly the hidden ground truth `x² + 3x − 5`, discovered purely through verifier-guided search.
- **Held-out accuracy: 1.0** (zero generalization gap), **calibration penalty: 0.0**, all anti-gaming checks passed.
- 2,537 distinct structures explored — the novelty archive kept diversity rising throughout the run.

### 9.1 Phase 2 findings: verification hardening

Running `eva/phase2_code_evolution.py` end-to-end against real code tasks surfaced exactly the kind of gap Section 6's threat model anticipates, verified by direct execution of the evolved candidates rather than by inspection:

- **A genuine memorization exploit** on `sum_to_n`: the evolved "best" (`min(n, 6) ** 2`) references the input variable — so it passed the original hardcode check — yet is wrong on ~98% of a wide integer range. Only a wide-range **probe split**, held out of the fitness signal entirely and used solely to gate harvest eligibility, exposes this.
- **A bloated-but-genuinely-correct formula** on `is_even`: convoluted boolean arithmetic that direct execution confirmed is actually correct everywhere. Not a correctness exploit — a parsimony gap. An Occam's-razor tiebreak (fitness first, AST size second) now suppresses this without a per-task special case.
- **A search-capability gap**, not a verification gap, on `sum_to_n`/`collatz_step`: pure AST mutation plateaus below solving these without the LLM hook. The fix that matters for *verification integrity* is refusing to launder that plateau as success — reports now carry an explicit `verified_for_harvest` gate (converged **and** generalizes on both held-out and probe splits) so an unconverged run is labeled `UNCONVERGED — do not harvest` rather than silently looking identical to a real win.

These are now permanent regressions in `eva/test_verifier_hardening.py`, per the L6 principle that every discovered specification-gaming incident becomes a regression test. Full writeup: `eva/README.md`.

## 10. Limitations & Open Questions

1. **Verifiability boundary.** The entire L1–L4 stack requires a computable fitness function. Extending verifiers toward fuzzy domains (fact-checkers with confidence scores, execution-based reasoning checks) is the highest-leverage open problem.
2. **Compute cost.** Population search is more expensive than a single DPO pass; justified on hard verifiable problems, wasteful for casual dialogue.
3. **Gaming moves up a level.** No design eliminates specification gaming; L6 treats it as a permanent adversarial process, not a solved problem.
4. **PRM label quality.** Step-level supervision needs its own verified step data — ideally bootstrapped from the same L1 loop.
