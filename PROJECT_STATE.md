# PROJECT STATE — compressed record of the full collaboration
**Read this first at the start of any new session.** Last updated: 2026-08-24.

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
- Actor never judges itself; judge never acts. Every claim carries its
  verification artifact (code + score + command).

## Current posture (2026-08-24)

- **Paid AI APIs PAUSED by user decision.** $0 engine is now a CHAIN, not a
  single key: `examples/free_engine.py` (stdlib-only, Termux-safe) falls back
  across Groq → Gemini → Cerebras → OpenRouter → GitHub Models → Mistral →
  local llama.cpp. Set ANY subset of the free keys (`.env.example` documents
  each); dead providers bench themselves for 5 min and the chain moves on.
  Both evolution loops use it; every trace records which provider answered
  (RLVR dataset traceability).
- Token discipline: no agents/tool calls unless the spend directly serves a
  stated goal; user asks "is this necessary?"

## Repo state (cloudesize67-cmd/OpenAlpha_Evolve)

- `76e911e` — `examples/torsion_filter/`: evaluator, seed, config, README.
- `892dd3b` — `physics_verification/grid_evaluator.py` + reference-free v2 task.
- `2cf7eb6` — `evaluator_termux.py` (pure-numpy twin) + TERMUX_SETUP.md.
- `4614c9f` — `candidate_a.py` + this file.
- 2026-08-06: `RESOURCE_PLAN.md` + `research/` bank: ALPHAEVOLVE_DATA_BRIEF,
  COSCIENTIST_DATA_BRIEF, SIMA2_DATA_BRIEF, SELF_HOSTED_BUILD_BLUEPRINT,
  **MASTER_ARCHITECTURE.md (six-layer plan — read second)**,
  NOESIS_BUILD_PLAN.md (Milestone B full design).
- 2026-08-06: `examples/torsion_filter/run_evolution.py` — Milestone A loop.
- 2026-08-06: `examples/noesis_coordination/` — generator + F1/ARI evaluator
  + seed; ladder verified (train: naive -0.147 < baseline 0.668 < strong
  1.489; held-out baseline collapses to 0.0, fusion 1.5).
- 2026-08-21: `core/free_model_router.py` (litellm-based router for the full
  OpenEvolve stack), `scripts/termux_local_model.sh` (llama.cpp + Qwen3-4B
  offline fallback), `research/FREE_MODEL_ACCESS.md`, `.env.example`.
- **2026-08-24 (SYSTEM COMPLETE):**
  - `examples/free_engine.py` — stdlib-only $0 fallback router (no litellm;
    urllib only). `--selftest` live-probes the chain; trust the probe, not
    marketing pages.
  - `examples/torsion_filter/run_evolution.py` REWIRED to the router chain.
  - `examples/noesis_coordination/run_evolution.py` NEW — Milestone B loop,
    full Law enforcement (preflight ladder gate, leak-audited prompts,
    deterministic subprocess judging, held-out never auto-run).
  - `research/COGNITIVE_ARCHITECTURE_DATA_BRIEF.md` — banked the "Artificial
    Cognition" synthesis (J-space/Hopfield/THDC/K3) with trust grading and
    six-layer mapping; one actionable import noted (trace-similarity
    retrieval over the RLVR bank — future, not scheduled).
  - Independent verifier: 10/10 gates PASS, zero Law violations, evaluators
    untouched. Mock-mode (`FREE_ENGINE_MOCK=1`) runs both loops offline.

## Verified numbers (benchmarks)

Torsion task, TRAIN_SEEDS (reproduced exactly, latest 2026-08-24):
naive MA 3.847 < engineer baseline 5.956 (termux evaluator); candidate_a
combined +12.13 (raw 18.09), held-out 17.92; seed initial_program -2.11.
NEVER mix numbers from the two evaluators in one table.
NOESIS task, TRAIN (verified 2026-08-24): naive -0.147 < engineer baseline
0.668 < strong fusion 1.489; seed program -0.015. HELD-OUT: baseline
collapses to 0.0, fusion 1.5.
Grid evaluator: reference 39.6, constants-cheat hard-fails, band-edge 45.6.

## Roadmap

- **Milestone A (ready to run):** pre-flight, then
  `python run_evolution.py --iterations 60`. Claim only the `--heldout`
  number.
- **Milestone B (ready to run):** same pattern in
  `examples/noesis_coordination/`. Synthetic-injector rung first; then
  FiveThirtyEight IRA tweets (zero-friction clone, positives only); then
  Zenodo ICWSM-2025 campaigns (access-gated: account + affiliation —
  submit request; one community college course unlocks both this and NSF
  ACCESS affiliation). Fork refs: QUT coordination-network-toolkit (MIT),
  VIGINUM D3lta (MIT). Coalition layer = aegis-net 5-agent repo. Target
  repo: cloudesize67-cmd/gemini.
- **Then:** NSF ACCESS Explore application (draft at
  /mnt/agents/output/NSF-ACCESS-Explore-Application-Draft.md).
- **NEVER lead with the SICQG quantum-gravity theory doc or consciousness
  framing** — untestable as written, harms credibility. Physics interest
  routes through instruments/engineering (the torsion task is the
  salvageable thread).

## Termux — exact recovery commands (copy each block separately, ONE at a time)

Update the repo:
```bash
cd ~/OpenAlpha_Evolve && git pull && cd examples/torsion_filter
```
Set every free key you have (any subset works; chain falls back
automatically). Gemini: aistudio.google.com/apikey — Groq:
console.groq.com — Cerebras: cloud.cerebras.ai — OpenRouter:
openrouter.ai/keys — Mistral: console.mistral.ai
```bash
export GEMINI_API_KEY="paste-key-here"
```
```bash
export GROQ_API_KEY="paste-key-here"
```
Probe the engine chain (trust the probe):
```bash
python ../free_engine.py --selftest
```
Milestone A gates, then the run:
```bash
python run_evolution.py --preflight-only
```
Gate: must print `naive MA : 3.847` and `engineer baseline: 5.956`, PASS.
```bash
python run_evolution.py --iterations 60
```
When it finishes it prints the held-out command — run it yourself; only
THAT number gets claimed:
```bash
python evaluator_termux.py --heldout checkpoints/best_program.py
```
Milestone B (same rhythm):
```bash
cd ~/OpenAlpha_Evolve/examples/noesis_coordination
```
```bash
python run_evolution.py --preflight-only
```
Gate: naive ≈ -0.147 < baseline ≈ 0.668 < strong ≈ 1.489, PASS.
```bash
python run_evolution.py --iterations 60
```
```bash
python evaluator.py --heldout checkpoints/best_program.py
```
Other useful flags: `--router-status` (which providers are live),
`FREE_ENGINE_MOCK=1` prefix (offline dry-run of the whole loop, no keys),
checkpoints mean a killed run resumes where it stopped — just re-run the
same command.

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
