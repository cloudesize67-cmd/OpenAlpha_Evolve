# RESEARCH BRIEF — SIMA 2 report: self-improvement loop patterns
Source analyzed: user-supplied AI-generated report "Architectural Framework
and Learning Dynamics of Google DeepMind's SIMA 2" (Google Docs artifact).
Analyzed: 2026-08-06. Fourth document in the research bank.
Primary sources cited inside: SIMA 2 tech report (arXiv:2512.04797),
DeepMind blog, Gemini Robotics 2 materials.

## 0. Trust calibration (per THE LAW)

LLM-generated synthesis. Grading:
- CONSISTENT WITH KNOWN PATTERN (trust directionally): actor/critic
  decoupling, experience bank, mixed-data anti-forgetting, synthetic task
  generation, Genie world-model synergy, gated research-preview rollout.
- UNVERIFIED SPECIFICS (leads only): exact training mixtures, Genie 3
  durations, specific game results, Apptronik Apollo 2 / Franka Duo claims,
  Gemini Robotics 2 model-card details.

## 1. Behavioral patterns

- Same AI-consultant register as the previous two reports (third instance —
  this is a genre the user is collecting deliberately).
- Same DeepMind gated rollout: limited research preview, restricted cohort,
  responsible-AI framing before capability detail. Third confirmation of the
  announce -> gate -> harvest-demand funnel.
- Third confirmation of THE universal pattern: actor separated from judge.
  AlphaEvolve: generator/deterministic evaluator. Co-Scientist: generation/
  reflection+ranking+lab. SIMA 2: actor/Gemini critic + experience bank.

## 2. Technology extracted (signal)

1. **Actor/critic decoupling**: SIMA 2 acts; Gemini estimates reward. The
   judge never acts; the actor never judges itself. (= THE LAW embodied.)
2. **Bank of self-generated experience**: every episode stored (states,
   actions, reasoning trace, reward); fine-tune on highest-reward
   trajectories; compounding improvement. DIRECTLY TRANSFERABLE: evolution
   runs produce verifier-scored code traces; bank as JSONL; later fine-tune
   a local sovereign model on them (RLVR pattern).
3. **Mixed-data training**: gameplay data + original pretraining data as
   regularization anchor against catastrophic forgetting. Rule for the
   future hardware phase: never fine-tune on project traces alone.
4. **Synthetic task generation**: the model invents its own tasks to map
   the environment's affordances. Top-of-stack role for the orchestrator:
   turn questions into scorable-task packages (ERA pattern from brief 3).
5. **Programmatic world models**: Genie 3 is a LEARNED infinite training
   ground. This project's equivalent is PROGRAMMATIC: make_trial() already
   generates infinite noise-worlds with free ground truth. For Milestone B:
   synthetic coordinated-behavior generator. Cheaper and verifiable.
6. **Admitted limits**: long-horizon drift, context-window loss,
   micro-precision. Mitigation pattern = externalized memory in files
   (this project's PROJECT_STATE.md pattern already implements it).
7. **Verbalized reasoning trace** as trust + debugging interface: agent
   narrates intent before acting. Cheap to adopt: every run log includes
   the "why" alongside scores (lineage JSONL, brief 3 item 8).

## 3. Fit into the master architecture

See research/MASTER_ARCHITECTURE.md — this brief feeds Layers 1, 5, and 6.

## 4. Noise discarded

Robotics hardware specifics (off-mission for now), marketing retellings
(MyMobileIndia, Medium), game-entertainment framing, works-cited padding.
