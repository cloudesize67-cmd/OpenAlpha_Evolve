# NOESIS BUILD PLAN — coordinated-manipulation detection system (Milestone B)
Synthesized: 2026-08-06 from two research waves (dataset inventory +
methods survey) + repo recon. Integrates research/MASTER_ARCHITECTURE.md.
Target repo: cloudesize67-cmd/gemini (currently README-only:
"NOESIS 5-agent counter-misinformation and market spoof detection system").
Coalition layer: cloudesize67-cmd/aegis-net (existing 5-agent POC pipeline).

## 0. Recon findings (what already exists)

- NOESIS = a name and a one-line README in the `gemini` repo. Nothing built.
- aegis-net = working 5-agent LLM chain (Sentinel -> Supervisor -> Auditor
  -> Verifier -> Architect) on Groq free tier + optional Anthropic, with
  HMAC-signed JSON outputs. GOOD bones, one Law violation: the Verifier is
  an LLM judging text. In the rebuild, LLM agents interpret; they NEVER
  score. Scoring is deterministic vs ground truth.
- "Market spoof detection" half of the NOESIS name: same architectural
  pattern applies (ground truth = SEC/enforcement cases), but DEFERRED.
  One domain proven end-to-end beats two half-built.

## 1. Ground truth (research wave R1, verified 2026-08-06)

| Source | Status | Use |
|---|---|---|
| Zenodo DOI 10.5281/zenodo.14141549 (ICWSM 2025; 26 takedown campaigns + matched controls; `is_control` label; 19-col CSVs of 50k posts) | GOLD STANDARD but access-gated: Zenodo account + academic affiliation + 1 file/day rate limit. Small campaigns: Armenia (…/14141550), Spain (…/14189086), Bangladesh (…/14188947). License CC BY-NC-ND 4.0; cite arXiv:2411.10609 | Phase 3 gold evaluation |
| FiveThirtyEight IRA tweets (github.com/fivethirtyeight/russian-troll-tweets): 13 CSVs, ~1.14 GB total, per-file ~94 MB, 2.97M tweets, 2,848 handles, 2012-2018, account_category labels | Zero-friction git clone; per-file processing is phone-feasible. GAP: positives only, no organic controls | Phase 2 ecological validation |
| Synthetic injector (we build it) | Infinite curriculum, perfect labels both ways | Phase 1 primary evaluator |
| TwiBot-22 | tens of GB, Drive-gated, weak-supervision labels — fails phone constraint | NSF ACCESS era only |
| Twitter/X IO archive | DEAD (confirmed; Zenodo is its successor) | — |
| Meta CIB | PDFs + IOC repo only, no account-level data | unusable for scoring |

Ground-truth ladder: synthetic (perfect labels, now) -> 538 IRA (real
positives, now) -> Zenodo campaigns (real positives + matched controls,
after affiliation). Each rung is a claim boundary; never claim a higher
rung's number from a lower rung's test.

## 2. Detection methods (research wave R2, verified 2026-08-06)

Three orthogonal, deterministically scorable signals (numpy/pandas/networkx
only — phone-feasible):

1. **Content duplication**: n-gram/Jaccard/simhash similarity between
   posts. References: CIB Mango Tree ngrams analyzer (thin — reimplement,
   don't depend), VIGINUM D3lta (github.com/VIGINUM-FR/D3lta, MIT, ships a
   LABELED synthetic dataset of 1.5M pairs with built-in P/R/F1 — free
   evaluation asset).
2. **Temporal synchronization**: per-account activity time series;
   co-occurrence within window w; Poisson statistical-surprise threshold
   (Magelinski et al. seed); DeBot's warped-correlation + lag-sensitive
   hashing (official code never released — reimplement in numpy, near-
   linear with LSH).
3. **Co-activity graph structure**: weighted account-account graph from
   signals 1-2 plus co-retweet/co-hashtag/co-link edges. Reference: QUT
   Coordination Network Toolkit (github.com/QUT-Digital-Observatory/
   coordination-network-toolkit, MIT, pip-installable, 6 network types,
   sqlite-backed, single machine). RULE: community detection stays FIXED
   (networkx louvain_communities, seed=0) OUTSIDE the evolved code, so
   scores are comparable across candidates.

Engineer baselines to beat (later, on TwiBot-scale data): Kantepe RF
F1 = 0.587, Varol Botometer-style RF — the "5.96 dB" equivalents for this
domain.

## 3. NOESIS on the six-layer architecture (all capabilities, simultaneous)

```
L5 TASK GENERATOR  -> scorable-task packages (this plan = the first one)
L4 AGENT COALITION -> aegis-net 5 agents, roles repaired:
     Sentinel  = input screening (unchanged)
     Supervisor= task decomposition (unchanged)
     Auditor   = interprets DETERMINISTIC OUTPUT — explains why the
                 pipeline flagged a cluster (evidence-linked)
     Verifier  = checks every claim traces to pipeline output; NOT a
                 scorer (Law repair)
     Architect = report synthesis (unchanged)
     Runs on Groq free tier (already proven in repo) or Kimi in-chat.
L3 EVOLUTION ENGINE-> OpenEvolve evolves heuristic functions inside
     EVOLVE-BLOCK: similarity fn, window/binning, edge weights,
     thresholds. Free-tier Gemini breadth now; local model later.
L2 DETERMINISTIC EVALUATORS (the firewall):
     - Account level: precision/recall/F1 vs labels, fixed seeds
     - Cluster level: adjusted Rand + homogeneity/completeness vs
       takedown account sets
     - Fitness ladder selftest gate (naive < baseline < strong), exactly
       like evaluator_termux.py's --selftest
     - Held-out = disjoint injection seeds + disjoint IRA files/years +
       (later) disjoint Zenodo campaigns. Claim held-out numbers ONLY.
L1 WORLD GENERATORS:
     - make_campaign(): the synthetic injector — organic background
       (Poisson activity, random topics) + injected coordinated groups
       (shared hashtags/URLs, sync within window w, noisy copypasta).
       Difficulty knobs: sync jitter, paraphrase rate, group size,
       background volume. Same design DNA as make_trial().
     - Real data per the ground-truth ladder above.
L0 MEMORY BANK     -> repo + lineage JSONL: every evolved heuristic +
     scores + parentage. Future RLVR fine-tuning dataset (SIMA 2 pattern).
```

## 4. Phased execution (all $0)

- **Phase 0 (this week, no LLM, no money):**
  1. git clone the 538 IRA repo (or download CSVs one at a time on phone).
  2. Build make_campaign() + evaluator v0 (account F1 + cluster ARI,
     fixed seeds, selftest gate). Pure numpy/pandas/networkx.
  3. Submit the Zenodo access request NOW (1 file/day rate limit = long
     pole; affiliation via the community-college route shared with NSF).
- **Phase 1:** hand-written seed heuristics for the 3 signals; verify the
  fitness ladder holds on synthetic data; freeze evaluator v1.
- **Phase 2:** OpenEvolve loop (free-tier Gemini key) evolves the
  heuristics; claim only held-out numbers. Ecological check: does the
  champion, never shown 538 data, cluster IRA handles by account_category?
- **Phase 3:** aegis-net coalition on top for interpretation + reporting;
  code lands in the `gemini` repo (NOESIS becomes real).
- **Phase 4 (hardware/NSF):** Zenodo gold evaluation, TwiBot-22 scale,
  local sovereign generator model fine-tuned on the lineage bank.

## 5. What runs TODAY at $0 vs what waits

Today: Phases 0-1 entirely (phone + free code), Zenodo request, plan.
Waits for free-tier key: Phase 2 evolution loop.
Waits for affiliation: Zenodo gold standard.
Waits for hardware/ACCESS: TwiBot-22, local models, RLVR fine-tune.

## 6. Noise discarded

CIB Mango Tree app scaffolding (GUI wrapper, only 2 real analyzers),
CooRTweet (R — port logic if needed), unlicensed academic notebooks
(Pacheco, Magelinski — use ideas, not code), Botometer API-dependent
tooling, Meta IOC repo, dead Twitter archive hunting.
