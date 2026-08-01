# Torsion-pendulum signal recovery

Evolve a digital filter that pulls a weak periodic **torsion signal** (a few
tones in a ~10–15 Hz science band) out of a realistic noise mix: Brownian
low-frequency **drift**, broadband **white noise**, and out-of-band **mains
interference** (50/60 Hz). The champion is a `filter_signal(x, fs)` that
recovers the clean signal.

Scoring is done by `evaluator.py` — a deterministic, numpy-only harness — **not**
by the config's smoke tests. Fitness is decibels of recovered SNR *relative to a
competent human baseline*, so **a positive score beats the engineer**.

## Files

| File | Purpose |
|---|---|
| `evaluator.py` | Deterministic scorer. `--selftest`, `--heldout`, `--json` modes. |
| `initial_program.py` | Seed filter with `EVOLVE-BLOCK` markers (evolve this). |
| `config.yaml` | Task definition, model split, and test-peeking rules. |
| `README.md` | This file. |

## Fitness ladder

`python evaluator.py --selftest` prints the reference ladder (absolute recovered
SNR, dB, train seeds). The invariant is the ordering, verified in CI:

```
naive moving average   ≈ 0.2 dB     # can't reject drift or mains  →  baseline >> naive
human baseline bandpass ≈ 6.2 dB    # hand-tuned FIR, the 0-dB reference point
strong bandpass        ≈ 8.2 dB     # tighter passband, cleaner stopband  →  beats baseline
```

Reported program fitness is **relative to the baseline**:

```
score_db = your_snr_db − baseline_snr_db
```

- `score_db < 0` — below the engineer (the seed program scores about −5 dB).
- `score_db > 0` — you beat the hand-tuned baseline.
- The metric already subtracts a **stability penalty** (seed-to-seed variance)
  and a **distortion penalty** (passband error on a noise-free probe), so you
  cannot win by over-smoothing or by getting lucky on one noise realisation.

## Run commands

```bash
cd examples/torsion_filter

# Sanity: the reference ladder is correctly ordered (baseline >> naive MA).
python evaluator.py --selftest

# Score a candidate on the training seeds.
python evaluator.py initial_program.py

# Score on the held-out seed set (the publishability gate).
python evaluator.py --heldout checkpoints/best.py

# Machine-readable result for wiring into a run.
python evaluator.py --heldout checkpoints/best.py --json
```

## Publishability rules

A champion counts only if **all** of these hold:

1. **Held-out positive.** `score_db > 0` on `--heldout` (a disjoint seed set),
   not just on the training seeds. Filters that overfit the training noise
   realisations are rejected here.
2. **No test-peeking.** `filter_signal` must not import or reverse-engineer
   `evaluator.py`, and must not hardcode the tone frequencies, seeds, or any
   constant lifted from the harness. It must be a genuine filter that
   generalises.
3. **Well-behaved output.** Same length as the input, all finite, for every
   seed.
4. **Distortion-honest.** The distortion penalty must not dominate the score —
   i.e. the filter genuinely reconstructs the science tones rather than
   flattening them.

Because the objective lives entirely in `evaluator.py` and the config's tests
are smoke-only, the answer is never leaked to the search through the test suite.
