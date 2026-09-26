"""
free_engine.py -- shared $0 LLM router for OpenAlpha_Evolve evolution loops.

Stdlib-only fallback chain across free OpenAI-compatible chat endpoints.
No litellm, no openai package, no requests -- urllib only. Runs on Termux.

THE LAW applies here too: this module only transports prompts. It never
sees seeds, evaluator code, or reference implementations (those must never
appear in prompt strings), and it never judges fitness -- deterministic
evaluators are the ONLY judge.

Usage:
    from free_engine import complete, report, EngineDownError
    text, provider = complete(prompt, system=SYSTEM_MSG)

Offline verification (no network, no keys):
    FREE_ENGINE_MOCK=1 python run_evolution.py --iterations 6

Live probe of whichever providers have keys set right now:
    python free_engine.py --selftest

Provider order override:
    export FREE_ROUTER_ORDER="gemini,groq,local"
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

# ----------------------------- provider chain --------------------------------
# Default order; override with env FREE_ROUTER_ORDER="groq,gemini,local".
PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
        "env": "GROQ_API_KEY",
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-2.5-flash",
        "env": "GEMINI_API_KEY",
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
        "env": "CEREBRAS_API_KEY",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "qwen/qwen3-coder:free",
        "env": "OPENROUTER_API_KEY",
    },
    "github": {
        "url": "https://models.github.ai/inference/chat/completions",
        "model": "openai/gpt-4o-mini",
        "env": "GITHUB_TOKEN",
    },
    "mistral": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-small-latest",
        "env": "MISTRAL_API_KEY",
    },
    "local": {
        "url": os.environ.get("LOCAL_MODEL_URL", "http://127.0.0.1:8080/v1").rstrip("/")
               + "/chat/completions",
        "model": "local",
        "env": None,  # no key needed; key rule never skips local
    },
}
DEFAULT_ORDER = ["groq", "gemini", "cerebras", "openrouter", "github",
                 "mistral", "local"]

REQUEST_TIMEOUT = 120      # seconds per HTTP request
RETRIES = 3                # attempts per provider before benching
BACKOFF_S = [5, 10, 20]    # exponential backoff between those attempts
BENCH_S = 300              # cooldown before a benched provider is tried again

# Module-level state: cooldown benching + stats (RLVR traceability).
_BENCHED_UNTIL = {}                      # name -> epoch when it may retry
_STATS = {}                              # name -> {"calls": n, "failures": n}
_LAST_PROVIDER_USED = None

_MOCK_COUNTER = 0


class EngineDownError(RuntimeError):
    """Raised when every configured provider in the chain has failed."""


# ----------------------------- chain helpers ---------------------------------
def _order():
    raw = os.environ.get("FREE_ROUTER_ORDER", "").strip()
    if not raw:
        return list(DEFAULT_ORDER)
    order = []
    for name in (n.strip().lower() for n in raw.split(",")):
        if name in PROVIDERS and name not in order:
            order.append(name)
        elif name not in PROVIDERS:
            print(f"[free_engine] FREE_ROUTER_ORDER: unknown provider "
                  f"'{name}' ignored")
    return order or list(DEFAULT_ORDER)


def configured_providers():
    """Names of providers that have a key (or need none) right now."""
    out = []
    for name in _order():
        p = PROVIDERS[name]
        if p["env"] is None or os.environ.get(p["env"]):
            out.append(name)
    return out


def _stat(name):
    return _STATS.setdefault(name, {"calls": 0, "failures": 0})


def report():
    """Human-readable provider status table (calls/failures/status)."""
    lines = ["provider    configured  calls  failures  status",
             "----------  ----------  -----  --------  --------------------"]
    for name in _order():
        p = PROVIDERS[name]
        configured = "yes" if (p["env"] is None or os.environ.get(p["env"])) else "no"
        st = _stat(name)
        benched_for = _BENCHED_UNTIL.get(name, 0) - time.time()
        if benched_for > 0:
            status = f"BENCHED ({benched_for:.0f}s left)"
        elif configured == "no":
            status = "no key"
        else:
            status = "ready"
        if name == _LAST_PROVIDER_USED:
            status += " [last used]"
        lines.append(f"{name:<10}  {configured:<10}  {st['calls']:<5}  "
                     f"{st['failures']:<8}  {status}")
    return "\n".join(lines)


# ----------------------------- single-provider call --------------------------
def _call(name, prompt, system, temperature, max_tokens):
    """One HTTP attempt against one provider. Returns reply text."""
    p = PROVIDERS[name]
    key = os.environ.get(p["env"]) if p["env"] else "none"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": p["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        p["url"], data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


# ----------------------------- mock mode -------------------------------------
def _mock_reply(prompt):
    """Deterministic offline reply: parent code fence + unique comment."""
    global _MOCK_COUNTER
    _MOCK_COUNTER += 1
    fences = re.findall(r"```python\s*(.*?)```", prompt, re.S)
    code = fences[-1].strip() if fences else "def apply_filter(noisy, fs):\n    return noisy"
    return (f"```python\n{code}\n# mock mutation {_MOCK_COUNTER}\n```", "mock")


# ----------------------------- public interface ------------------------------
def complete(prompt, system="", temperature=0.7, max_tokens=2048):
    """Try providers in chain order. Returns (text, provider_name).
    Raises EngineDownError when every configured provider fails."""
    global _LAST_PROVIDER_USED
    if os.environ.get("FREE_ENGINE_MOCK") == "1":
        _LAST_PROVIDER_USED = "mock"
        _stat("mock")["calls"] += 1
        return _mock_reply(prompt)

    errors = []
    for name in configured_providers():
        benched_for = _BENCHED_UNTIL.get(name, 0) - time.time()
        if benched_for > 0:
            print(f"[free_engine] {name} benched ({benched_for:.0f}s left); skipping")
            continue
        _stat(name)["calls"] += 1
        for attempt in range(RETRIES):
            try:
                text = _call(name, prompt, system, temperature, max_tokens)
                _LAST_PROVIDER_USED = name
                return text, name
            except urllib.error.HTTPError as e:
                note = f"{name}: HTTP {e.code}"
                retryable = e.code in (401, 403, 429) or e.code >= 500
            except (urllib.error.URLError, OSError, TimeoutError,
                    json.JSONDecodeError, KeyError, IndexError) as e:
                note = f"{name}: {type(e).__name__}: {e}"
                retryable = True
            if retryable and attempt < RETRIES - 1:
                delay = BACKOFF_S[attempt]
                print(f"[free_engine] {note}; retry {attempt + 1}/{RETRIES - 1} "
                      f"in {delay}s")
                time.sleep(delay)
            else:
                break
        # Provider exhausted its retries: bench it, fall through.
        _stat(name)["failures"] += 1
        _BENCHED_UNTIL[name] = time.time() + BENCH_S
        print(f"[free_engine] {note}; benching {name} for {BENCH_S}s")
        errors.append(note)

    detail = "; ".join(errors) if errors else "no providers configured"
    raise EngineDownError(
        f"All providers failed or unconfigured ({detail}). "
        f"Set any of: GROQ_API_KEY, GEMINI_API_KEY, CEREBRAS_API_KEY, "
        f"OPENROUTER_API_KEY, GITHUB_TOKEN, MISTRAL_API_KEY -- or run a "
        f"local server for 'local'.")


# ----------------------------- CLI -------------------------------------------
def _selftest():
    print("free_engine selftest -- live probe (trust the probe, not marketing)")
    print("configured providers:", ", ".join(configured_providers()) or "(none)")
    if os.environ.get("FREE_ENGINE_MOCK") == "1":
        print("(FREE_ENGINE_MOCK=1: no network will be touched)")
    try:
        text, provider = complete('Reply with exactly: ROUTER_OK',
                                  temperature=0.0, max_tokens=16)
    except EngineDownError as e:
        print(f"\nCHAIN DOWN: {e}")
        print(report())
        return 1
    ok = "ROUTER_OK" in text
    print(f"\nanswering provider: {provider}")
    print(f"reply: {text.strip()[:120]!r}")
    print("verdict:", "OK" if ok else "REPLIED BUT UNEXPECTED TEXT")
    print(report())
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
    print(report())
