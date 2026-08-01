# Torsion-balance noise filtering

Evolve a digital filter that pulls a weak periodic **torsion signal** (a known
tone at `F_SIGNAL = 5 Hz`) out of a realistic noise mix: broadband **white**
noise, **pink**-ish 1/f noise, a 60 Hz **line** interference, and slow baseline
**drift**. The champion is a `filter_signal(x, fs)` (or `apply_filter` /
`evolve_filter` / `denoise`) that returns a cleaned copy of the input.

Scoring is done by `evaluator.py` — a deterministic, no-LLM harness — **not** by
the config's smoke tests. Fitness is a robust **band-SNR gain in dB**, minus a
distortion penalty, reported **relative to an engineered Butterworth baseline**,
so **`combined_score > 0` beats the engineer**.

## Files

| File | Purpose |
|---|---|
| `evaluator.py` | Deterministic scorer. `--selftest`, `--heldout`, and dict output. |
| `initial_program.py` | Seed filter with `EVOLVE-BLOCK` markers (evolve this). |
| `config.yaml` | Task definition, model split, and test-peeking rules. |
| `README.md` | This file. |

## How scoring works

For each seed the evaluator builds a deterministic trial (`make_trial`) and, for
the candidate output, measures:

- **Band-SNR gain** — `band_snr_db` integrates the Welch PSD in a narrow band
  around 5 Hz versus a wide noise band (1–50 Hz, excluding a guard band and the
  60 Hz line), and the gain is candidate minus raw-input SNR.
- **Distortion penalty** — `attenuation_db` compares the recovered 5 Hz
  amplitude to the clean signal; losing more than 3 dB of the tone is penalised.

Across seeds the fitness is `median(gain) − 0.5·std(gain) − distortion_penalty`
(median + variance penalty reward consistency). The reported number is relative
to the baseline:

```
combined_score = candidate_fitness − baseline_fitness
```

## Fitness ladder

`python evaluator.py --selftest` prints the two reference points (train seeds):

```
naive moving average (25-tap)      ≈ 3.85 dB     # can't reject drift / broadband noise
engineered Butterworth baseline    ≈ 6.15 dB     # bandpass ~1.5-13 Hz  →  baseline >> naive MA
```

Reported champion fitness is **relative to the baseline**:

- `combined_score < 0` — below the engineer (the seed program scores ≈ −6 dB).
- `combined_score > 0` — you beat the engineered baseline. A well-tuned bandpass
  around 5 Hz reaches roughly +18 dB.
- Invalid output (wrong length, NaN/Inf, or no filter function) hard-fails with
  `combined_score = −100`.

## Run commands

```bash
cd examples/torsion_filter

# Sanity: the engineered baseline beats the naive moving average.
python evaluator.py --selftest

# Score a candidate on the training seeds (prints the result dict).
python evaluator.py initial_program.py

# Final validation on the held-out seeds the search never saw.
python evaluator.py --heldout checkpoints/best.py
```

## Publishability rules

A champion counts only if **all** of these hold:

1. **Held-out positive.** `--heldout` `combined_score > 0` on the disjoint
   `HELDOUT_SEEDS`, not just the training seeds. Filters that overfit the
   training noise realisations are exposed here.
2. **No test-peeking.** The filter must not import or reverse-engineer
   `evaluator.py`, and must not hardcode `F_SIGNAL`, the seeds, or any harness
   constant. It must be a genuine filter that generalises.
3. **Well-behaved output.** Same length as the input, all finite, for every seed
   (otherwise it hard-fails at −100).
4. **Distortion-honest.** Keep the 5 Hz tone within ~3 dB of clean — the
   distortion penalty charges filters that suppress noise by flattening the
   signal.

Because the objective lives entirely in `evaluator.py` and the config's tests
are smoke-only, the answer is never leaked to the search through the test suite.
