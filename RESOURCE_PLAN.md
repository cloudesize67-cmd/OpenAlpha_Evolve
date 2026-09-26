# RESOURCE PLAN — free-capability map for the goal chain
**Read alongside PROJECT_STATE.md.** Last updated: 2026-08-06.
Goal chain: proof-of-concept results -> NSF ACCESS compute allocation ->
funded research benefiting U.S. citizens.

## Current posture

- **Outside paid AI models: PAUSED by user decision (2026-08-06).** No Gemini /
  Claude / paid API calls for running tasks. The OpenEvolve API loop
  (Milestone A part 2) is on hold until a $0 engine is chosen.
- THE LAW still governs everything: credibility = demonstrated prediction
  against independent ground truth. Deterministic evaluators only. Held-out
  numbers only. No seed/test leakage into prompts.

## Tier 0 — capabilities already in this chat ($0 marginal cost)

| Capability | What it does for the project |
|---|---|
| Web research (Kimi built-in) | Finds datasets, papers, docs, funding programs; no extra cost |
| GitHub research (MCP tools) | Searches all public repos, reads code, forks/pushes files. Same class of capability as Kimi Claw's repo research |
| Sandbox compute (Kimi ipython) | Runs numpy/pandas analysis, verifies evaluator numbers BEFORE user types anything on Termux (pre-flight rehearsal, done 2026-08-06: all gate numbers reproduced exactly) |
| Memory layer | Auto-loaded every session: working rules, the Law, repo state, roadmap, English-only, cost discipline |
| PROJECT_STATE.md (repo root) | The single focused access point: compressed record of all substantive work. New sessions read it first |
| Termux + numpy evaluator | Deterministic scoring on the phone, free, no compilation (scipy-free twin) |

## Tier 1 — free external assets, mapped to milestones

### Milestone A (torsion filter, evolutionary search)
- Evaluator: verified and frozen. Gate numbers reproduced 2026-08-06 in
  Kimi sandbox: naive MA 3.847 < baseline 5.956; candidate_a +12.13 combined,
  17.92 held-out.
- Engine options at $0 (choose one when ready):
  1. **Free-tier LLM keys** (e.g. Google AI Studio free tier) driving the real
     OpenEvolve loop within rate limits. Cleanest publishable claim.
  2. **In-chat evolution**: Kimi proposes filter variants, sandbox evaluator
     scores them, elites kept. Good for building the loop and intuition —
     but NOT a blind run (Kimi has seen the evaluator code), so its numbers
     are development numbers, never publishable champions. Honesty rule.

### Milestone B (blind re-discovery POC: coordinated manipulation)
Ground truth located 2026-08-06, all free:
- **Zenodo DOI 10.5281/zenodo.14141549** — ICWSM 2025 "Labeled Datasets for
  Research on Information Operations": 26 verified platform-takedown IO
  campaigns, 16 state actors, WITH matched control accounts, anonymized,
  `is_control` label column. Ideal blind test: strip labels, detect, score
  vs labels. This is the primary target.
- **Twitter/X Information Operations archive** — 37+ attributed takedown
  datasets, 17 countries, 200M+ tweets (2018-2021 disclosures; existing
  datasets remain downloadable). Kaggle mirror: "Twitter Election Data
  Archives".
- **Meta Adversarial Threat Reports / CIB archive** —
  transparency.meta.com/metasecurity/threat-reporting/ — ongoing quarterly
  takedown reports (report-level ground truth, not post-level).
- **TwiBot-22** (github.com/LuoUndergradXJTU/TwiBot-22, NeurIPS 2022
  benchmark, official repo) — labeled bot-detection benchmark for a second,
  independent ground truth.
- **CIB Mango Tree** (cibmangotree.org) — open-source library for
  coordinated-behavior detection; candidate fork for detection-method code.

### Funding and context
- **NSF ACCESS Explore** draft: /mnt/agents/output/NSF-ACCESS-Explore-Application-Draft.md.
  Compute is free once allocated; needs U.S. institutional affiliation
  (cheapest: one community college course).
- **Data plugins in this chat** (IMF, World Bank, scholar, SEC EDGAR,
  Yahoo Finance): free macro/funding-landscape numbers for the application
  narrative (AI + quantum are the protected funding categories).

## Tier 2 — paused (costs money, resume only by user decision)

- Paid LLM API calls for large-scale evolution runs (breadth generation).
- Strong-model elite refinement (the 20% slice in config.yaml).

## Integration architecture (the focused access point)

```
GitHub repo (cloudesize67-cmd/OpenAlpha_Evolve)
  = single source of truth
    PROJECT_STATE.md   <- what the project is (read first, every session)
    RESOURCE_PLAN.md   <- this file: what resources exist, what they cost
    examples/          <- tasks, evaluators, candidates
Kimi K3 = orchestrator: memory + research + sandbox verification + writing
Termux  = free deterministic execution (numpy evaluator, git pull)
Free-tier LLM APIs = evolution engine (when unpaused)
Public datasets (Zenodo / X archive / Meta / TwiBot-22) = ground truth
NSF ACCESS = compute scale-up after POC numbers exist
```

## Next actions menu (all $0)

1. Termux pre-flight (3 blocks from PROJECT_STATE.md) — confirms the phone
   side reproduces the verified gate numbers.
2. Download the Zenodo IO dataset (DOI above), inspect schema, design the
   Milestone B deterministic evaluator (detection score vs `is_control`
   ground truth, held-out campaigns).
3. Decide the $0 evolution engine for Milestone A (free-tier key vs
   in-chat development loop).
4. Paste any old chat content worth mining; it gets folded into
   PROJECT_STATE.md.
