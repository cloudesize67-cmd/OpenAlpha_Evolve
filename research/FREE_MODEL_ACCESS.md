# Free Model Access — Research Bank (verified 2026-08-21)

Purpose: the engine runs at $0/month. This note records which free LLM
tiers actually exist, their real limits, and the rules for trusting them.
The router that implements this lives in `core/free_model_router.py`;
the offline fallback installer lives in `scripts/termux_local_model.sh`.

## Core law applied here

Credibility = demonstrated prediction against independent ground truth.
Free-tier marketing pages are claims, not ground truth. Therefore:

1. The router logs which provider actually answered every call.
2. Run `python -m core.free_model_router` before any evolution run — the
   live probe is the verdict, not this table.
3. Never hardcode one provider's model name anywhere else in the codebase.
   Cerebras cut its free catalog from ~12 models to 2 in a single week in
   2026 without notice. Assume every free roster rotates monthly.
4. Providers marked "trains on data" must NEVER see evaluator seeds, held-out
   test cases, or reference implementations. Route sensitive prompts to
   Groq/Cerebras (no-training policies) or the local model.

## Tier table (snapshot — re-probe before trusting)

| Provider | Free quota | Card? | Trains on your data? | Best role |
|---|---|---|---|---|
| Groq | ~30 RPM, ~1,000 req/day, TPM is the real ceiling | No | No | Primary: fast mutations |
| Google AI Studio (Gemini 2.5 Flash) | ~10 RPM, up to ~1,500 req/day, 1M ctx | No | Yes (free tier) | Long-context prompts only |
| Cerebras | ~1M tokens/day, 8K ctx cap | No | No | High-volume batch |
| OpenRouter `:free` | 20 RPM, 50 req/day (1,000/day after one-time $10) | No | No (ZDR default) | Safety net / model variety |
| GitHub Models | 15 RPM, 150–1,000 req/day | No | No | Frontier-model experiments only (terms) |
| Mistral (free tier) | per-model caveats | No | Yes (Experiment tier) | Coding workloads |
| Cloudflare Workers AI | 10K neurons/day shared | No | No | Embeddings / edge |
| Local llama.cpp (Termux) | Unlimited, offline | — | Never | Final fallback; seed-safe |

## Cost discipline rules (budget law)

- Cheap/free models for breadth (candidate generation), strong models only
  for elite refinement. On $0, "strong" = Gemini 2.5 Flash long context or
  a GitHub Models frontier call — spend those scarce daily requests only at
  the final selection stage.
- Order matters: Groq first (fast + no training), Gemini for anything that
  needs long context, Cerebras for bulk, OpenRouter/GitHub/Mistral as
  spares, local as outage insurance.
- When a provider dies mid-run, the router benches it 5 minutes and falls
  through. The engine must treat a total chain failure as "back off and
  retry later" — never fabricate a candidate.

## Setup checklist

1. `pip install litellm` (already in requirements).
2. Create free keys: console.groq.com, aistudio.google.com/apikey,
   cloud.cerebras.ai, openrouter.ai/keys — none require a card.
3. Export the ones you have:
   `export GROQ_API_KEY=... GEMINI_API_KEY=... CEREBRAS_API_KEY=... OPENROUTER_API_KEY=...`
4. Probe: `python -m core.free_model_router` → expect PASS + provider table.
5. Offline insurance: `bash scripts/termux_local_model.sh` (one-time ~2.5 GB
   model download, then `bash scripts/termux_local_model.sh run`).
6. Wire into CodeGeneratorAgent: replace its direct `acompletion` call with
   `FreeModelRouter().complete(...)`, or pass the router's chosen model
   string through the existing litellm path.

## Sources

- OpenRouter, "Free LLM API in 2026: 13 Options Ranked" (2026-06)
- klymentiev.com, "Free LLM APIs in 2026: 13 Providers Compared" (2026-04)
- merginit.com, "Free AI APIs 2026" (2026-06)
- pricepertoken.com Cerebras/Cloudflare free-tier pages (2026)
- wotai.co, "Best free LLM APIs 2026 (live-probed)" (2026-07)
- ianlpaterson.com, live-probe snapshot (2026-05-31)
