# MASTER ARCHITECTURE — the sovereign self-improving research system
Synthesized: 2026-08-06, from the four-source research bank
(ALPHAEVOLVE_DATA_BRIEF, COSCIENTIST_DATA_BRIEF,
SELF_HOSTED_BUILD_BLUEPRINT, SIMA2_DATA_BRIEF).
This is THE plan. Read after PROJECT_STATE.md.

## The one-sentence version

Separate the actor from the judge, let the actor evolve, let the judge be
deterministic ground truth, bank every verified experience, and compound.

Google runs this pattern three times (AlphaEvolve: code; Co-Scientist:
ideas; SIMA 2: embodied skills) with datacenters. This project runs the
same pattern sovereign: phone + free-tier API + this repo.

## The six layers

```
LAYER 5  TASK GENERATOR (ERA / self-tasking role)
         Turns questions into scorable-task packages:
         {seed program + deterministic evaluator + config + metric}
         Now: Kimi orchestrator writes them. Exists: torsion_filter,
         quantum_gravity_scaling_v2. Next: manipulation detection (Milestone B)

LAYER 4  AGENT COALITION (Co-Scientist role)
         Generate / debate / verify ideas. Supervisor = Kimi K3 with
         persistent memory. Research, review, verify subagents on demand.
         Elo/LLM judgment ONLY where no metric exists, and validated
         against ground truth before being trusted (the Law).

LAYER 3  EVOLUTION ENGINE (AlphaEvolve role)
         OpenEvolve: prompt sampler + LLM ensemble (cheap breadth /
         strong depth) + MAP-Elites program DB + islands + cascade.
         Mutations inside EVOLVE-BLOCK only. Model-agnostic: free-tier
         Gemini key now, local open-weights model later (config change).

LAYER 2  DETERMINISTIC EVALUATORS (the firewall)
         Scalar scores from code execution only. Verified on Termux:
         evaluator_termux.py (gate numbers reproduced 2026-08-06).
         Hallucination cannot cross this layer. Synthetic claims are
         re-validated under claim boundaries (--heldout now; real-data
         swap later per README rule 4).

LAYER 1  WORLD GENERATORS (Genie role, but programmatic)
         make_trial() today: infinite noise-worlds with known ground
         truth, 30 lines of numpy, free. Milestone B: synthetic
         coordinated-behavior generator + public takedown ground truth
         (Zenodo DOI 10.5281/zenodo.14141549, TwiBot-22, X IO archive).

LAYER 0  PERSISTENT MEMORY BANK (SIMA 2 experience-bank role)
         - This repo: PROJECT_STATE.md + research/ bank + code = record
         - Kimi memory layer: working rules, auto-loaded every session
         - Run lineage: JSONL of every candidate + score + parentage
           (to add when the engine runs — cheap, auditable, and it is
           the future fine-tuning dataset)
```

## The compounding loop (how the system self-improves)

1. Layer 5 emits a scorable task. 2. Layer 3 evolves candidate solutions;
   Layer 2 scores them deterministically. 3. Champions are claimed ONLY on
   held-out ground truth. 4. Every trace (code + score + lineage) deposits
   into Layer 0. 5. When hardware arrives (Tier 1 GPU box or NSF ACCESS),
   Layer 0's verified traces fine-tune a local model (RLVR-style; mix in
   general data per SIMA 2 anti-forgetting rule). 6. The improved local
   model becomes Layer 3's generator -> better candidates -> better traces.
   The flywheel SIMA 2 runs on games, this system runs on science.

## Hardware tiers (unchanged from blueprint, restated against layers)

- Tier 0 (now, $0): S23+ runs Layers 1-2; free-tier Gemini = Layer 3
  generator; Kimi = Layers 4-5; repo = Layer 0. COMPLETE system.
- Tier 1 (~$400-800 used, later): 24GB GPU box -> Layer 3 goes sovereign
  (Qwen2.5-Coder-32B-class quantized); Layer 6 fine-tuning begins.
- Tier 2 (NSF ACCESS, $0): datacenter scale for Layers 3+6.

Invariant across tiers: Layers 0-2 stay local, deterministic, sovereign.
Only the generation layer migrates.

## The credibility ladder (what the outside world sees)

1. Milestone A: held-out number, evolved filter beats engineer baseline.
   One-command reproduce. (Waiting on: free-tier API key + Termux
   pre-flight.)
2. Milestone B: blind re-discovery scored vs public takedown ground truth.
   (No LLM needed to start: download Zenodo dataset, build evaluator.)
3. NSF ACCESS Explore application citing: verified POC numbers + the
   pattern lineage (AlphaEvolve/Co-Scientist/SIMA 2) + the $0 replication
   story. Reviewer doubts answered one-per-result, Co-Scientist
   case-study style.

## Rules that must never break (the Law, operationalized)

1. Deterministic evaluators only, where a metric exists.
2. Held-out numbers only in public claims.
3. No seeds/tests/reference implementations in prompts.
4. Validate any auto-metric against ground truth before trusting it.
5. Actor never judges itself; judge never acts.
6. Every claim carries its verification artifact (code + score + command).
