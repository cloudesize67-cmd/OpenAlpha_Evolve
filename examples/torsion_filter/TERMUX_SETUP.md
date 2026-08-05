# Running the POC on Termux (Android)

scipy fails to build on Termux — that's why `evaluator_termux.py` exists:
pure numpy, same seeds, same scoring as `evaluator.py`.

## Setup (5 commands)

```bash
pkg update && pkg upgrade -y
pkg install -y python python-numpy git        # use the PREBUILT numpy — never pip-install numpy on Termux
git clone https://github.com/cloudesize67-cmd/OpenAlpha_Evolve.git
cd OpenAlpha_Evolve/examples/torsion_filter
python evaluator_termux.py --selftest
```

**Self-test must print** (numbers from my verification run):
```
naive MA        : 3.847
engineer baseline: 5.956
```
If baseline is not clearly above naive MA, stop — something is wrong with
the install, not the math.

## Optional: the evolution loop

```bash
pip install openevolve                 # pure-python; if a dep fails, see below
termux-wake-lock                       # keep CPU awake during the run
python openevolve-run.py initial_program.py evaluator_termux.py \
    --config config.yaml --iterations 40
```

- Point `config.yaml`'s evaluator at `evaluator_termux.py` (not evaluator.py).
- Set your API key first (`export OPENAI_API_KEY=...` or per your provider).
- Phone-friendly settings: population 8–12, iterations 40, one island.
  Each evaluation is seconds; a full run is an evening, not a week.
- If `openevolve` won't install: the evaluator still works standalone —
  have your Claude Code session write candidate filters to files and score
  them with `python evaluator_termux.py candidate.py`. Same loop, manual crank.

## Scoring a champion (the publishable number)

```bash
python evaluator_termux.py --heldout best_candidate.py
```

Report that number — and only that number — as the result.

## Known-good reference numbers (2026-08-02 verification)

| Filter | Robust fitness (dB), TRAIN_SEEDS |
|---|---|
| naive moving average (seed) | 3.85 |
| engineer baseline (FIR LP @12 Hz) | 5.96 |
| numpy FIR bandpass 3.5–6.5 Hz | 18.09 (held-out 17.92) |

A scipy build of the same evaluator gives slightly different absolute dB
(different filter shapes); within one evaluator, comparisons are exact.
Never mix numbers across the two evaluators in one table.
