# BUILD BLUEPRINT — duplicating the AlphaEvolve + Co-Scientist architecture
# on own hardware
Source: user-supplied AI-generated report "Accessing AlphaEvolve AI
Capabilities" (Google Docs artifact, ~14 web sources, unverified secondhand).
Analyzed: 2026-08-06. Companion to ALPHAEVOLVE_DATA_BRIEF.md and
COSCIENTIST_DATA_BRIEF.md.

## 0. Trust calibration of the source (per THE LAW)

The source is LLM-generated synthesis with no deterministic evaluator behind
it. Claims graded:
- MATCHES PRIMARY SOURCES (trust): four-module architecture, EVOLVE-BLOCK
  delimiters, MAP-Elites program DB, evaluation cascade, Flash-breadth/
  Pro-depth ensemble, client-side runner split, 0.7% Borg / rank-48 /
  32.5% FlashAttention figures.
- UNVERIFIED LEADS (do not cite until checked): Coolblue/FM Logistic/
  Kinaxis/PacBio/Spanner enterprise numbers; JetBrains B-tree case details
  (17.4s->16.6s, 2-of-5 survival, 50+ iterations/session); GA status and
  "Agent-as-multiplier" pricing; GigaEvo DAG+Redis details; PAT/ScholarPeer
  STOC/NeurIPS stats (35%/31%); Genesis Mission deployment timeline;
  Antigravity AlphaEvolve Skill; ERA/Flat-UCB-Tree-Search specifics.

## 1. Behavioral patterns of the document

- AI-generated consultant register ("executive summary", "it is imperative",
  exhaustive coverage signaling, works-cited list).
- Vendor-funnel attention distribution: 4 of 5 "pathways" route through
  Google products; the sovereign open-source path gets 1 of 5. Invert for
  this project: Pathway 3 (open-source) is the main road.
- Credibility-by-number, secondhand: precise corporate figures without
  primary citations inline — pattern matches Google's own launches but the
  specific numbers are unverified.
- Trustworthy core = the architecture sections, which match the white paper
  and this repo's files point-for-point.

## 2. The composite architecture (the two systems, one blueprint)

Co-Scientist layer (ideas, no deterministic metric):
  supervisor + persistent memory + task queue
    -> Generation / Proximity / Reflection / Ranking(Elo) / Evolution /
       Meta-review agents
    -> output: formalized hypothesis handed downstream

ERA glue (per source, unverified specifics): hypothesis -> "scorable task"
package = {problem description, scoring metric, train/validation data}.

AlphaEvolve layer (code, deterministic metric):
  prompt sampler (parents + inspirations + scores + self-reflection)
    -> LLM ensemble (cheap breadth + strong depth; diff/SEARCH-REPLACE
       mutations inside EVOLVE-BLOCK only)
    -> program database (MAP-Elites + island model + migration)
    -> evaluator pool (deterministic, client-side, scalar scores)
    -> champions re-validated under claim boundaries
       (synthetic claims != integration claims)

Firewall principle (source quote, matches THE LAW): deterministic code
execution is "an absolute firewall against the propagation of theoretical
hallucinations into production."

## 3. What this project ALREADY owns (gap analysis, 2026-08-06)

| Component | Status |
|---|---|
| Supervisor + persistent memory | HAVE: Kimi orchestrator + PROJECT_STATE.md + Kimi memory |
| Idea generate/debate/evolve | HAVE at $0: chat research/review/verify agents |
| Scorable-task package | HAVE: initial_program.py + evaluator_termux.py + config.yaml |
| Prompt sampler | COMES FREE with OpenEvolve (engine not yet running) |
| LLM ensemble | GAP: free-tier Gemini key needed (aistudio.google.com/apikey) |
| Program DB (MAP-Elites/islands) | HAVE in config: 3 islands, elite selection, cascade on |
| Evaluator pool | HAVE + VERIFIED: Termux numpy twin, gate numbers reproduced |
| Claim boundaries | HAVE: --heldout; TODO later: real-data swap (README rule 4) |

The one missing piece to a running system: the free-tier API key.

## 4. Self-hosted engineering rules extracted

1. Generative and evaluation halves are separable; only scores cross the
   wire. Keep generation swappable (API now, local models later).
2. Start EVOLVE-BLOCK scope narrow; widen as the archive populates.
3. Audit the fixed skeleton for memory leaks — slow leaks crash automated
   cascades after hundreds of iterations (critical on a phone).
4. Evaluation cascade: cheap syntax/shape checks first, expensive scoring
   for survivors only (already in config).
5. Sandbox untrusted evolved code: subprocess + timeout (60s already) +
   no network for candidate code. Vertex AI Code Execution is Google's
   managed version; ours is simpler and local.
6. Claim boundaries: synthetic-optimized winners must survive integration
   testing before any public claim (JetBrains pattern: 2 of 5 survived).
7. Island migration topology (source table): exploration = 10+ islands /
   migrate every ~25 epochs / ~20% elites; exploitation = 3-5 islands /
   ~100 epochs / ~5%. Current config = exploitation posture; raise
   diversity if the search stalls.
8. Lineage tracking (GigaEvo idea): persist every candidate + score +
   parentage; auditable "why did this win" = credibility asset. Cheap to
   add: JSONL log per run.

## 5. Hardware tiers (acquire later, plan now)

- Tier 0 (now, $0): Galaxy S23+/Termux = full evaluator half. Generation =
  free-tier Gemini. Complete system, not a toy.
- Tier 1 (~$400-800 used): 24GB GPU box (used RTX 3090 class). Runs local
  open-weights coder models (Qwen2.5-Coder-32B quantized class) via
  llama.cpp/Ollama. OpenEvolve is model-agnostic: change the model name in
  config.yaml, generation becomes sovereign, per-token cost -> $0.
  Storage: 512GB+ SSD; 64GB RAM comfortable for 801-tap FIR evaluation
  batches + local model offload.
- Tier 2 (NSF ACCESS, $0 after allocation): datacenter GPUs for full-scale
  runs; the draft application already exists. Genesis Mission section of
  the source is evidence of the federal demand pattern.

Architecture invariant across all tiers: evaluation stays local,
deterministic, and sovereign; only the generation layer migrates.

## 6. Noise discarded

Enterprise pricing speculation, FedRAMP/CMMC compliance detail, IDE
integration pathway, PAT/ScholarPeer peer-review tooling (interesting but
off-mission), WPP/Composio/Medium retellings in the works-cited list.
