# Torsion-Balance Denoise — Milestone A Task

Evolve a noise-subtraction filter for a torsion-pendulum-style readout.
Target: recover a known 5 Hz signal buried in white + 1/f + 60 Hz line +
drift noise.

## Why this task

It has the one property that makes evolutionary search honest: a **fast,
objective, deterministic evaluator**. No LLM judges fitness.

## Fitness ladder (verified on TRAIN_SEEDS, 2026-08-02)

| Filter | Robust fitness (dB) |
|---|---|
| 45 Hz lowpass (naive engineer) | 0.79 |
| 25-tap moving average (seed) | 3.85 |
| **12 Hz lowpass (competent engineer = baseline)** | **6.12** |
| 2–8 Hz bandpass (strong engineer) | 8.81 |

`combined_score` = candidate fitness − 6.12. **> 0 beats the competent
engineer. > 2.7 beats a strong engineer.** Publish the held-out number
(`python evaluator.py --heldout best_program.py`), not the train number.

## Run

```bash
pip install openevolve numpy scipy
python evaluator.py --selftest          # must show baseline >> naive MA
python openevolve-run.py initial_program.py evaluator.py \
    --config config.yaml --iterations 60
# when a champion emerges:
python evaluator.py --heldout checkpoints/best.py
```

## Rules that keep the result publishable

1. Never paste evaluator code or seeds into prompts.
2. Champions are only claimed on HELDOUT_SEEDS.
3. One-command Docker reproduce before showing anyone.
4. When real torsion-balance data exists, swap `make_trial()` for logged
   sensor data and drop `F_SIGNAL` to the real frequency (e.g. ~2.5 mHz) —
   evaluation time then tracks the acquisition window, so cut iterations
   and lean on cascade evaluation.
