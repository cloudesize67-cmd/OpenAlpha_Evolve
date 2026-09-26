# NOESIS Coordination Detection — Milestone B Scorable Task

Evolve a detector for coordinated inauthentic behavior: groups of accounts
posting near-duplicate content in synchronized bursts with shared
signature hashtags, hidden among organic users and decoy fan communities.

Part of the six-layer master architecture (research/MASTER_ARCHITECTURE.md):
this is a Layer-5 scorable-task package = {seed + deterministic evaluator +
world generator}. Full design: research/NOESIS_BUILD_PLAN.md.

## Why this task

Same property as the torsion task: a fast, objective, DETERMINISTIC
evaluator. No LLM judges fitness. make_campaign() is the programmatic
world generator (the Genie role, free): infinite campaigns with perfect
two-way ground truth.

## Fitness ladder (verified in sandbox, 2026-08-06)

Metric = account-level F1 + 0.5 * ARI(over IO accounts). Max 1.5.

| Detector | TRAIN metric | HELD-OUT metric |
|---|---|---|
| naive frequency (seed-level) | -0.147 (robust agg) | 0.0 |
| **engineer baseline: content-only k=4 Jaccard** | **0.668** | **0.0** |
| strong fusion (content+sync+tags) | 1.489 | 1.500 (perfect) |

`combined_score` = candidate metric - 0.668. **> 0 beats the engineer.**
The claim boundary: held-out campaigns are HARDER (more paraphrase, more
jitter, more decoys) — the content-only baseline COLLAPSES to 0.0 there.
Publish the held-out number only:
`python evaluator.py --heldout checkpoints/best.py`

## Candidate contract

Define `detect_campaign(posts) -> list of clusters` (lists of account ids;
clusters of size >= 2 count as flagged). Posts: list of dicts
{"account": int, "t": float, "tokens": tuple[int], "tags": tuple[int]}.
Pure stdlib + numpy only (Termux-safe: no pandas, no networkx, no scipy).

## Run

```bash
python evaluator.py --selftest          # must show naive < baseline < strong
python evaluator.py initial_program.py  # seed: combined_score ~ -0.02
python openevolve-run.py initial_program.py evaluator.py \
    --config ../torsion_filter/config.yaml --iterations 60
python evaluator.py --heldout checkpoints/best.py
```

## Rules that keep the result publishable (the Law)

1. Never paste evaluator code, generator code, seeds, or ground truth
   into prompts. Optimize the general problem, not the test.
2. Community detection (if any) inside candidates must be deterministic
   (fixed thresholds / connected components; no stochastic algorithms).
3. Champions are claimed on HELDOUT_SEEDS with HELDOUT difficulty only.
4. Ground-truth ladder for public claims: synthetic (this) -> 538 IRA
   real positives -> Zenodo ICWSM-2025 campaigns with matched controls.
   Never claim a higher rung from a lower rung's test.
