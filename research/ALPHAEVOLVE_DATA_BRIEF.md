# RESEARCH BRIEF — AlphaEvolve page, endpoints mapped and data harvested
Source analyzed: Google DeepMind blog, "AlphaEvolve: A Gemini-powered coding
agent for designing advanced algorithms" (May 14, 2025).
Collected: 2026-08-06. Purpose: data store for later use (Milestone A engine
decision, NSF ACCESS narrative, evaluator design patterns).

## 1. Behavioral pattern analysis of the source page

- **Credibility-by-number**: every claim carries a hard, evaluator-verified
  figure (0.7% compute recovery, 23% kernel speedup, 32.5% FlashAttention
  speedup, rank-48 matrix algorithm, 593-sphere kissing configuration).
  This is THE LAW operating at Google scale: claim only what a deterministic
  evaluator scored.
- **Authority anchors**: Terence Tao, Jordan Ellenberg in acknowledgements —
  borrowed mathematical credibility.
- **Gated-access funnel**: blog announces capability -> white paper establishes
  priority -> registration form harvests demand data from academics -> Colab
  releases verification artifacts but NOT the system. The Early Access form is
  itself a data-collection instrument. Google demonstrates, withholds, and
  collects. Confirmed at endpoint level: the results repo explicitly states
  "This repository does not contain the code to run AlphaEvolve."
- **Architecture mirror**: "Gemini Flash maximizes breadth, Gemini Pro provides
  critical depth" = the cheap-80%/strong-20% model split already in
  examples/torsion_filter/config.yaml. Independent convergence on the same
  cost-discipline design — citable in the NSF narrative.

## 2. Endpoint map (every link on the page, resolved)

| Page link | Actual endpoint | What is there | Value |
|---|---|---|---|
| "white paper" | arXiv:2506.13131 (Jun 16, 2025); PDF at storage.googleapis.com | Full technical report: pipeline, prompt sampling, program DB, evaluators, ablations | HIGH — engineering spec |
| "mathematical results in our Google Colab" | github.com/google-deepmind/alphaevolve_results | `mathematical_results.ipynb` + verification code for each SOTA-breaking construction; explicitly NO agent code | HIGH — verification-code patterns to copy |
| "Register your interest" form | Google Forms early access | Demand-collection instrument; academic users only | LOW for now — needs institutional affiliation |
| FunSearch reference (2023) | Romera-Paredes et al., Nature | Predecessor: single-function evolution | MEDIUM — genealogy for paper writing |
| (found via research) OpenEvolve | github.com/algorithmicsuperintelligence/openevolve | Mature open-source AlphaEvolve implementation; pip installable; the engine config.yaml already targets | HIGHEST — the $0 engine |
| (found) second fork | github.com/ryanrudes/openevolve | MIT-licensed, codebase-scale, built on FunSearch Apache-2.0 code | MEDIUM — alternative fork |

## 3. Applicable technology (signal, not noise)

Transferable engineering patterns, in priority order for this project:

1. **OpenEvolve runs on the Gemini FREE TIER.** Default setup: get key at
   aistudio.google.com/apikey, `export OPENAI_API_KEY="<gemini key>"`, run
   `openevolve-run.py`. This answers the paused Milestone A engine question:
   the real, publishable OpenEvolve loop can run at $0 within free-tier rate
   limits. No paid models required.
2. **Empirical ensemble finding** (from OpenEvolve replication): fast cheap
   model for most generations + occasional strong model gives best results;
   low latency matters more than peak quality for breadth. Cost data point:
   Gemini-2.5-Flash ~ $0.01-0.05/iteration; free tier covers exploration.
   Third-party validation of the config.yaml model split.
3. **Evaluation cascade**: cheap tests first, expensive scoring only for
   survivors. Already in config (`cascade_evaluation: true`) — keep it; it
   is the main cost lever on free-tier rate limits.
4. **Artifact side-channel**: feed runtime errors back into the next prompt.
   OpenEvolve has this (`enable_artifacts`); it accelerates convergence
   without extra models. Turn it on when running.
5. **MAP-Elites + island populations**: quality-diversity archive prevents
   premature convergence; islands with ring migration. Matches config
   (`num_islands: 3`). Justification reference for NSF narrative.
6. **Deterministic seeding end-to-end** (LLM, database, evaluation all
   seeded; default seed=42): this is what makes a run reproducible for
   reviewers. Adopt the same discipline in run logs.
7. **Verification-artifact pattern**: DeepMind published constructions +
   verifier code but not the agent. For Milestone A/B the equivalent is:
   publish champion code + held-out score + one-command reproduce; the
   search machinery can stay private. Copy this disclosure pattern.
8. **Evolve the search algorithm, not the object**: AlphaEvolve's math wins
   came from evolving heuristic search programs, not constructions directly.
   Design principle for future tasks (Milestone B detection heuristics).

## 4. Data to store for later use

NSF ACCESS narrative numbers (verified, citable to arXiv:2506.13131):
- 0.7% of Google's worldwide compute recovered by an evolved scheduling
  heuristic, in production >1 year. = the economic argument for
  evolutionary search on real infrastructure.
- 23% speedup on a Gemini matrix-multiply kernel; 1% total training-time
  reduction; kernel optimization time cut from weeks of expert effort to
  days of automated experiments.
- 32.5% speedup on FlashAttention GPU instructions (domain humans avoid).
- Rank-48 algorithm for 4x4 complex matrix multiplication; first improvement
  over Strassen in this setting in 56 years; SOTA improved on 14 matrix
  targets.
- 50+ open math problems: ~75% SOTA rediscovered, ~20% improved.
- OpenEvolve replication: circle packing n=26 reached 2.634 vs DeepMind's
  2.635 (99.97%) — proof the open implementation reproduces the frontier.

References to cite:
- Novikov et al., arXiv:2506.13131 (AlphaEvolve white paper)
- Romera-Paredes et al. 2023 (FunSearch, Nature)
- Sharma 2025, github.com/algorithmicsuperintelligence/openevolve (OpenEvolve)
- google-deepmind/alphaevolve_results (verification artifacts)

## 5. Noise discarded

Footer marketing, model catalog, illustrations, "transformative" language
without numbers, podcast/video summaries, Medium retellings. None collected.
