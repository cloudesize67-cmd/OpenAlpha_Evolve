"""
FreeModelRouter — $0/month LLM access layer for OpenAlpha_Evolve.

Purpose
-------
The evolution engine needs an LLM it can call for free, indefinitely,
without a credit card. No single free tier is reliable enough to depend on
(rate limits shrink, free catalogs rotate without notice — Cerebras dropped
from ~12 free models to 2 in one week in 2026). So the router treats free
providers as a *chain*: try the first configured provider, and on
rate-limit / auth / server failure, cool it down and fall through to the
next. Providers with no API key set are skipped silently.

Engineering rule enforced here (per PROJECT law):
  credibility = demonstrated prediction against independent ground truth.
The router therefore LOGS which provider actually answered every call, and
ships a self-test (`python -m core.free_model_router`) that probes the
chain live and prints a verdict table. Never trust a provider's marketing
page; trust the probe.

Usage inside the engine
-----------------------
    from core.free_model_router import FreeModelRouter

    router = FreeModelRouter()
    text, provider = await router.complete("Write a Python function that ...")
    # CodeGeneratorAgent integration: pass router as a callable, or read
    # router.last_model_string and feed it to litellm.acompletion directly.

Environment variables (set only the ones you have keys for)
-----------------------------------------------------------
    GEMINI_API_KEY      aistudio.google.com/apikey   (no card)
    GROQ_API_KEY        console.groq.com             (no card)
    CEREBRAS_API_KEY    cloud.cerebras.ai            (no card)
    OPENROUTER_API_KEY  openrouter.ai/keys           (no card for :free models)
    GITHUB_TOKEN        github.com/settings/tokens   (GitHub Models, free)
    MISTRAL_API_KEY     console.mistral.ai           (free experiment tier)
    FREE_ROUTER_ORDER   optional comma list to reorder/skip providers,
                        e.g. "groq,gemini,local"
    LOCAL_MODEL_URL     default http://127.0.0.1:8080/v1 (llama.cpp server,
                        see scripts/termux_local_model.sh)

Free-tier snapshot (verified by research 2026-08; re-probe before trusting):
    Gemini AI Studio  ~10 RPM, up to ~1,500 req/day, 1M ctx, trains on data
    Groq              ~30 RPM, ~1,000 req/day, ~6K TPM ceiling, no training
    Cerebras          ~1M tokens/day, 8K ctx cap on free tier, no training
    OpenRouter :free  20 RPM, 50 req/day (1,000/day after one-time $10)
    GitHub Models     15 RPM, 150-1,000 req/day, prototyping-terms only
    Mistral           free tier, per-model caveats, trains on Experiment tier
    local (llama.cpp) unlimited, offline, small models only — final fallback
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from litellm import acompletion
from litellm.exceptions import (
    APIError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# How long a failed provider stays benched before it may be retried (s).
DEFAULT_COOLDOWN_SECONDS = 300


@dataclass
class ProviderSpec:
    """One link in the free fallback chain."""
    name: str                     # human label, used in logs and ORDER
    model: str                    # litellm model string
    env_key: Optional[str]        # env var holding the API key (None = keyless)
    extra: Dict[str, Any] = field(default_factory=dict)  # base_url etc.
    note: str = ""


def _default_chain() -> List[ProviderSpec]:
    """Ordered cheapest-effort-first chain. Override with FREE_ROUTER_ORDER."""
    return [
        ProviderSpec(
            name="groq",
            model="groq/llama-3.3-70b-versatile",
            env_key="GROQ_API_KEY",
            note="fast (300+ tok/s), 30 RPM / ~1,000 req/day, no training on data",
        ),
        ProviderSpec(
            name="gemini",
            model="gemini/gemini-2.5-flash",
            env_key="GEMINI_API_KEY",
            note="1M context, up to ~1,500 req/day; Google trains on free-tier data",
        ),
        ProviderSpec(
            name="cerebras",
            model="cerebras/gpt-oss-120b",
            env_key="CEREBRAS_API_KEY",
            note="~1M tokens/day but 8K context cap; free catalog rotates — probe first",
        ),
        ProviderSpec(
            name="openrouter",
            model="openrouter/qwen/qwen3-coder:free",
            env_key="OPENROUTER_API_KEY",
            note="50 req/day free; :free roster rotates; 1,000/day after $10 top-up",
        ),
        ProviderSpec(
            name="github",
            model="openai/gpt-4o-mini",
            env_key="GITHUB_TOKEN",
            extra={"base_url": "https://models.github.ai/inference"},
            note="GitHub Models free tier; terms limit to experimentation/prototyping",
        ),
        ProviderSpec(
            name="mistral",
            model="mistral/mistral-small-latest",
            env_key="MISTRAL_API_KEY",
            note="free experiment tier; per-model caveats, may train on data",
        ),
        ProviderSpec(
            name="local",
            model="openai/local-model",
            env_key=None,  # llama.cpp server needs no key
            extra={
                "base_url": os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:8080/v1"),
                "api_key": "none",
            },
            note="Termux llama.cpp fallback (scripts/termux_local_model.sh); "
                 "unlimited but weakest model — last resort",
        ),
    ]


class FreeModelRouter:
    """
    Fallback router across free LLM tiers.

    - Skips providers whose key is not configured.
    - On failure, benches that provider for `cooldown_seconds`, then moves on.
    - Records per-provider stats so evolution runs can report exactly which
      model produced which candidate (traceability for the RLVR dataset).
    """

    def __init__(self, cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS):
        self.cooldown_seconds = cooldown_seconds
        chain = _default_chain()
        order = os.getenv("FREE_ROUTER_ORDER")
        if order:
            wanted = [n.strip() for n in order.split(",") if n.strip()]
            by_name = {p.name: p for p in chain}
            chain = [by_name[n] for n in wanted if n in by_name]
            unknown = set(wanted) - set(by_name)
            if unknown:
                logger.warning("FREE_ROUTER_ORDER contains unknown providers: %s", unknown)
        self.providers: List[ProviderSpec] = chain
        self._cooldown_until: Dict[str, float] = {}
        self.stats: Dict[str, Dict[str, int]] = {
            p.name: {"calls": 0, "failures": 0} for p in self.providers
        }
        self.last_provider_used: Optional[str] = None

    # ------------------------------------------------------------------ #
    def _available(self, p: ProviderSpec) -> bool:
        if p.env_key and not os.getenv(p.env_key):
            return False
        return time.time() >= self._cooldown_until.get(p.name, 0)

    def _bench(self, name: str) -> None:
        self._cooldown_until[name] = time.time() + self.cooldown_seconds
        self.stats[name]["failures"] += 1

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        generation_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """
        Try each configured provider in order.

        Returns (text, provider_name). Raises RuntimeError if the whole
        chain is down — the engine should treat that as 'no free capacity
        right now', back off, and retry later (never fake a result).
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        kwargs = {"temperature": temperature, "max_tokens": max_tokens}
        kwargs.update(generation_kwargs or {})

        errors: List[str] = []
        for p in self.providers:
            if not self._available(p):
                continue
            try:
                logger.info("FreeModelRouter: trying provider '%s' (%s)", p.name, p.model)
                resp = await acompletion(
                    model=p.model, messages=messages, **kwargs, **p.extra
                )
                if not resp.choices:
                    raise APIError("empty choices", llm_provider=p.name, model=p.model)
                text = resp.choices[0].message.content or ""
                self.stats[p.name]["calls"] += 1
                self.last_provider_used = p.name
                logger.info("FreeModelRouter: provider '%s' answered (%d chars)",
                            p.name, len(text))
                return text, p.name
            except (RateLimitError, AuthenticationError, BadRequestError,
                    InternalServerError, APIError, TimeoutError) as e:
                logger.warning("FreeModelRouter: '%s' failed: %s — benching %ds",
                               p.name, e, self.cooldown_seconds)
                self._bench(p.name)
                errors.append(f"{p.name}: {type(e).__name__}")
                continue
            except Exception as e:  # unexpected — still bench and fall through
                logger.error("FreeModelRouter: '%s' unexpected error: %s",
                             p.name, e, exc_info=True)
                self._bench(p.name)
                errors.append(f"{p.name}: {type(e).__name__}")
                continue

        raise RuntimeError(
            "All free providers exhausted. Errors: " + "; ".join(errors or ["none configured"])
        )

    def report(self) -> str:
        lines = ["provider   calls  failures  status"]
        for p in self.providers:
            if p.env_key and not os.getenv(p.env_key):
                status = "no key"
            elif time.time() < self._cooldown_until.get(p.name, 0):
                status = "cooldown"
            else:
                status = "ready"
            s = self.stats[p.name]
            lines.append(f"{p.name:<10} {s['calls']:>5}  {s['failures']:>8}  {status}")
        return "\n".join(lines)


async def _self_test() -> None:
    """Live probe of the chain. Trust the probe, not the marketing page."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    router = FreeModelRouter()
    probe = "Reply with exactly: ROUTER_OK"
    print("Configured providers:", [p.name for p in router.providers if router._available(p)])
    try:
        text, provider = await router.complete(probe, temperature=0.0, max_tokens=16)
        verdict = "PASS" if "ROUTER_OK" in text else "WEAK (answered but off-instruction)"
        print(f"\nProvider that answered: {provider}")
        print(f"Response: {text!r}")
        print(f"Verdict: {verdict}")
    except RuntimeError as e:
        print(f"\nCHAIN DOWN: {e}")
        print("Set at least one free API key (see module docstring) "
              "or start the local model server.")
    print("\n" + router.report())


if __name__ == "__main__":
    import asyncio
    asyncio.run(_self_test())
