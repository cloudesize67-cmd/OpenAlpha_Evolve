# PROJECT STATE — compressed record of the full collaboration
**Read this first at the start of any new session.** Last updated: 2026-08-06 (evening).

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
- 2026-08-06 additions: actor never judges itself; judge never acts. Every
  claim carries its verification artifact (code + score + command).

## Current posture (2026-08-06)

- **Paid AI APIs PAUSED by user decision.** $0 engine path confirmed:
  OpenEvolve runs on the Gemini FREE TIER (key: aistudio.google.com/apikey,
  exported as OPENAI_API_KEY). The one missing piece for Milestone A part 2.
- Token discipline: no agents/tool calls unless the spend directly serves a
  stated goal; user asks "is this necessary?"

## Repo state (cloudesize67-cmd/OpenAlpha_Evolve)

- `76e911e` — `examples/torsion_filter/`: evaluator, seed, config, README.
- `892dd3b` — `physics_verification/grid_evaluator.py` + reference-free v2 task.
- `2cf7eb6` — `evaluator_termux.py` (pure-numpy twin) + TERMUX_SETUP.md.
- `4614c9f` — `candidate_a.py` + this file.
- 2026-08-06: `RESOURCE_PLAN.md` (root) + `research/` bank:
  ALPHAEVOLVE_DATA_BRIEF, COSCIENTIST_DATA_BRIEF, SIMA2_DATA_BRIEF,
  SELF_HOSTED_BUILD_BLUEPRINT, **MASTER_ARCHITECTURE.md (the six-layer plan —
  read second)**, NOESIS_BUILD_PLAN.md (Milestone B full design).
- 2026-08-06 (late): `examples/torsion_filter/run_evolution.py` — self-
  contained Milestone A loop on Gemini free tier (numpy-only, no openevolve
  install). Sandbox-verified: preflight reproduces 3.847/5.956 exactly, seed
  scores -2.11, mock candidate scored +2.79, traces + checkpoints + resume
  all work. Enforces the Law: no seed/evaluator leaks into prompts, held-out
  never auto-run.

## Verified numbers (benchmarks)

Torsion task, TRAIN_SEEDS (reproduced in Kimi sandbox 2026-08-06, exact):
naive MA 3.847 < engineer baseline 5.956 (termux evaluator); candidate_a
combined +12.13 (raw 18.09), held-out 17.92; seed initial_program -2.11.
NEVER mix numbers from the two evaluators in one table.
Grid evaluator: reference 39.6, constants-cheat hard-fails, band-edge 45.6.

## Roadmap

- **Milestone A:** pre-flight on Termux (commands below; sandbox-verified
  2026-08-06), then `run_evolution.py --iterations 60` on free-tier Gemini
  key; claim only the `--heldout` number.
- **Milestone B (NOESIS): FULL PLAN EXISTS — research/NOESIS_BUILD_PLAN.md.**
  Ground-truth ladder: synthetic injector (make_campaign(), we build) ->
  FiveThirtyEight IRA tweets (zero-friction clone, positives only) ->
  Zenodo ICWSM-2025 campaigns w/ is_control labels (access-gated: account +
  affiliation + 1 file/day — submit request NOW). Methods: content
  duplication + temporal synchronization + co-activity graph (community
  detection FIXED, seed=0, outside EVOLVE-BLOCK). Fork refs: QUT
  coordination-network-toolkit (MIT), VIGINUM D3lta (MIT, has labeled
  synthetic pairs). Coalition layer = aegis-net 5-agent repo (roles repaired:
  LLMs interpret, never score). Target repo: cloudesize67-cmd/gemini.
- **Then:** NSF ACCESS Explore application (draft at
  /mnt/agents/output/NSF-ACCESS-Explore-Application-Draft.md). ACCESS needs
  U.S. institutional affiliation — cheapest route = one community college
  course (same affiliation unlocks Zenodo dataset access).
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
Want: `combined_score` ≈ +12.1, held-out ≈ 17.9. That is pre-flight PASS.

Milestone A part 2 (the evolution run itself):
```bash
export GEMINI_API_KEY="paste-your-free-key-here"
```
```bash
python run_evolution.py --preflight-only
```
```bash
python run_evolution.py --iterations 60
```
When it finishes, the held-out command is printed — run it yourself and only
THAT number gets claimed.

Termux survival rules: `$` = shell (commands go here); `>>>` = inside Python
(`exit()` to leave); blank cursor with no `$` = inside `cat` (Volume Down + D
to leave); `exit` at `$` closes the session; Volume Down = Ctrl in Termux;
paste ONE block at a time; outputs shown for comparison are never typed.

## Where things live

- Persistent memory instructions: saved in Kimi (project, the Law, repo
  state, roadmap, working style, master-architecture pointer) —
  auto-available in new sessions.
- This file + RESOURCE_PLAN.md + research/ bank: GitHub repo.
- Chat sidebar saving is handled by the Kimi app automatically; earlier
  separate chats are only visible to Kimi as short snippets — all substantive
  work is in THIS project's thread and captured in this file.
