# RESEARCH BRIEF — Co-Scientist page: behavioral patterns + extracted ideas
Source analyzed: Google DeepMind blog, "Co-Scientist: A multi-agent AI
partner to accelerate research" (May 19, 2026).
Collected: 2026-08-06. Companion to ALPHAEVOLVE_DATA_BRIEF.md.
Purpose: pattern library + design ideas for the mission (Milestone B,
NSF narrative, orchestration architecture).

## 1. Behavioral patterns in the source page

- **Same launch funnel as AlphaEvolve** (template confirmed, not one-off):
  announce -> Nature paper (priority) -> labs.google/science registration
  form (demand harvesting, same instrument as AlphaEvolve early access)
  -> case studies as proof.
- **Testimonial saturation architecture**: six professors / six institutions
  (Stanford, MIT, Cambridge, Edinburgh, Calico, Abudayyeh-Gootenberg).
  Each quote is engineered to neutralize one specific buyer objection:
  coverage ("read everything"), agency ("structure my thoughts"), scale
  ("team of 50 people in a day"), trust ("thinks like a scientist"),
  replacement fear ("can't do science by itself").
  LESSON for NSF writing: each POC result should answer one specific
  reviewer doubt, the same way.
- **Softer numbers than AlphaEvolve, deliberately**: hypothesis quality has
  no deterministic metric, so wet-lab validation substitutes as ground truth
  (drug-repurposing candidates confirmed in lab; 91% scarring-response
  block; Advanced Science publication). THE LAW adapted: no metric ->
  validate against physical reality.
- **Safety pre-positioning**: CBRN misuse evals, custom safety classifiers,
  "partner not replacement", "users are responsible". Liability-shifting and
  regulatory framing placed before any regulator asks.
- **Reveal the orchestra, hide the instruments**: six-agent architecture
  published; prompts, code, tournament parameters withheld. Same disclosure
  posture as AlphaEvolve (results repo without agent code).

## 2. The architecture (what they disclosed)

Supervisor agent (adaptive planner, parallel coordination) orchestrating:
  GENERATE: Generation agent (hypotheses from literature+data)
            Proximity agent (clusters hypotheses for diverse coverage)
  DEBATE:   Reflection agent ("virtual peer reviewer")
            Ranking agent (Elo tournament, pairwise simulated debates,
            principles borrowed from AlphaGo/AlphaStar)
  EVOLVE:   Evolution agent (refines/combines top-ranked hypotheses)
            Meta-review agent (synthesizes debates, writes final proposal)
Tools integrated: web search, ChEMBL, UniProt, AlphaFold (select collabs).
Enterprise preview: Daiichi Sankyo, Bayer Crop Science, US National
Laboratories (Genesis Mission). 100+ institutions involved in development.

## 3. Mapping to this project (why it matters)

| Co-Scientist piece | Project equivalent |
|---|---|
| Generation + Proximity (diversity) | OpenEvolve population + num_islands/MAP-Elites |
| Reflection (peer reviewer) | review subagents in this chat |
| Ranking (Elo tournament) | cross-validation; but see Law below |
| Evolution (refine winners) | the evolutionary loop, on ideas vs code |
| Meta-review (synthesis) | report integration / NSF writing |
| Supervisor | Kimi K3 orchestrator role |
| ChEMBL/UniProt tools | IMF/World Bank/scholar plugins |

The user is already running a $0 Co-Scientist: orchestrated research,
review, verification agents + deterministic evaluators.

## 4. Ideas extracted (signal)

1. **Compute-allocation principle**: "the majority of the system's
   computation is dedicated to verifying." THE LAW as a budget policy.
   Project consequence: generation = cheap/free-tier; evaluation =
   rigorous deterministic (already free). Current budget structure is
   already aligned.
2. **Validated-proxy rule origin**: Elo tournament = LLM-judged ranking;
   Google validated it against benchmark ground truth before trusting it.
   This is the source of the project's "validate any auto-metric against
   ground truth" rule (PROJECT_STATE, the Law).
3. **Two engine types, keep them separated**:
   - AlphaEvolve mode: evolve CODE where a deterministic evaluator exists
     (torsion filter, detection heuristics).
   - Co-Scientist mode: generate/debate/evolve INTERPRETATIONS where no
     metric exists — never for scoring.
   Milestone B design: deterministic scoring vs takedown ground truth;
   LLM layer only for meaning-making around deterministic outputs.
4. **Proximity-agent idea for Milestone B**: cluster flagged accounts/
   behaviors BEFORE ranking, to guarantee coverage of distinct
   coordination strategies (anti-echo-chamber for detection).
5. **Disclosure pattern (repeated)**: publish champion + verification,
   withhold machinery. Same as AlphaEvolve brief item 7.

## 5. Data stored for later (NSF narrative)

- Case-study writing template: problem -> system contribution ->
  validated result -> one-doubt-killing quote.
- "Majority of compute on verification" — citable design principle
  (Nature paper, Gottweis & Natarajan et al., 2026).
- Genesis Mission tie-in: US National Laboratories are already enterprise
  preview users — evidence that US national labs fund/adopt exactly this
  class of system. Supports the NSF ACCESS argument.

## 6. Noise discarded

Portraits, footer marketing, duplicate image captions, related-posts
carousel, podcast/catalog links.
