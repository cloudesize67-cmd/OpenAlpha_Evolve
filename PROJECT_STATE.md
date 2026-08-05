# PROJECT STATE — compressed record of the full collaboration
**Read this first at the start of any new session.** Last updated: 2026-08-02.

## Who & what this is

User: GitHub `cloudesize67-cmd` (Michael A.). Background: high school diploma
+ some college, works on Android/Termux, budget is tight. Self-described
strengths: recognizing platform/data-collection behavior, propaganda patterns,
psychology, history. Weakness: math calculation (Kimi carries arithmetic and
teaches math tied to the project: probability/stats → linear algebra →
information theory).

**Goal chain:** proof-of-concept results → NSF ACCESS compute allocation →
funded research benefiting U.S. citizens. Strategic context: U.S. GDP ~2%
(IMF WEO), debt heading to 142% of GDP by 2031, but AI + quantum are the
protected funding categories; compute is being given away via credit programs
because hyperscalers are supply-constrained and desperate for useful workloads.

## THE LAW (governs everything)

**Credibility = demonstrated prediction against independent ground truth.**
- Deterministic evaluators only — never LLM-as-judge where a metric exists.
- Publish held-out numbers ONLY. Never train scores.
- Never leak seeds, tests, or reference implementations into prompts.
- Validate any auto-metric against ground truth before trusting it
  (AlphaEvolve evaluator pattern; Google AI co-scientist Elo-vs-GPQA pattern;
  cf-PICI blind re-discovery pattern).

## Repo state (cloudesize67-cmd/OpenAlpha_Evolve)

- `76e911e` — `examples/torsion_filter/`: `evaluator.py` (scipy version,
  scores dB relative to engineer baseline), `initial_program.py` (seed with
  EVOLVE-BLOCK), `config.yaml` (cheap-model breadth / strong-model elite
  refinement), `README.md` (fitness ladder, rules).
- `892dd3b` — `physics_verification/grid_evaluator.py` (champion scorer for
  the quantum-gravity toy task: log-log regression of scaling exponents +
  divergence score, held-out ranges) + `examples/quantum_gravity_scaling_v2.yaml`
  (reference-free task prompt; reference implementation REMOVED from prompt
  because it leaked the answer).
- `2cf7eb6` — `examples/torsion_filter/evaluator_termux.py` (pure-numpy twin;
  scipy won't build on Termux) + `TERMUX_SETUP.md`.
- Latest — `examples/torsion_filter/candidate_a.py` (reference numpy FIR
  bandpass candidate) + this file.

## Verified numbers (benchmarks)

Torsion task, TRAIN_SEEDS: naive MA 3.85 < engineer baseline 5.96 (termux
evaluator) / 6.12 (scipy evaluator) < strong bandpass 8.81; candidate_a raw
~18.1, held-out ~17.9. NEVER mix numbers from the two evaluators in one table.
Grid evaluator: reference 39.6, constants-cheat hard-fails, band-edge 45.6.

## Roadmap

- **Milestone A (NOW):** score `candidate_a.py` on Termux (pre-flight), then
  run the OpenEvolve loop so AI *discovers* a filter beating the 5.96
  baseline; claim only the `--heldout` number.
- **Milestone B:** blind re-discovery POC — strip labels from a documented
  coordinated-manipulation campaign, system flags it blind, score vs public
  takedown ground truth (mirrors Google's cf-PICI design at $0).
- **Then:** NSF ACCESS Explore application (draft at
  /mnt/agents/output/NSF-ACCESS-Explore-Application-Draft.md). Note: ACCESS
  needs U.S. institutional affiliation — cheapest route = one community
  college course. NOESIS repo (misinformation system) is README-only for now.
- **NEVER lead with the SICQG quantum-gravity theory doc** — untestable as
  written, harms credibility. Physics interest routes through instruments/
  engineering (the torsion task is the salvageable thread).

## Termux — exact recovery commands (copy each block separately)

```bash
cd ~/OpenAlpha_Evolve && git pull && cd examples/torsion_filter
```
```bash
python evaluator_termux.py --selftest
```
Gate: must print `naive MA : 3.847` and `engineer baseline: 5.956`.
```bash
python evaluator_termux.py candidate_a.py && python evaluator_termux.py --heldout candidate_a.py
```
Want: `combined_score` ≈ +12, held-out ≈ 17.9. That is pre-flight PASS.

Termux survival rules: `$` = shell (commands go here); `>>>` = inside Python
(`exit()` to leave); blank cursor with no `$` = inside `cat` (Volume Down + D
to leave); `exit` at `$` closes the session; Volume Down = Ctrl in Termux;
paste ONE block at a time; outputs shown for comparison are never typed.

## Where things live

- Persistent memory instructions: saved in Kimi (project, the Law, repo
  state, roadmap, working style) — auto-available in new sessions.
- This file: GitHub repo root (PROJECT_STATE.md) + /mnt/agents/output/.
- Chat sidebar saving is handled by the Kimi app automatically; earlier
  separate chats are only visible to Kimi as short snippets — all substantive
  work is in THIS project's thread and captured in this file.
