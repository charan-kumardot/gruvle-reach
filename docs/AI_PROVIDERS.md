# AI providers

`app/providers/ai/` implements the `AIProvider` interface. The rest of the
app (`app/agents/*`) only ever calls `generate_json` / `generate_text` on
whatever `get_ai_provider()` returns — switching providers is a one-line env
change, no code changes.

## Ollama (default)

Free, fully local, no API key. Install from [ollama.com](https://ollama.com),
run `ollama serve` (or let the app auto-start it on some platforms), and pull
a chat-capable model:

```bash
ollama pull llama3.1
```

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

This repo was verified end-to-end (product understanding → ICP generation)
against `qwen3:8b` and `qwen3:4b` as well. Any model that follows JSON-mode
instructions reasonably well will work — the app instructs the model to
respond with JSON via `format: "json"` in the Ollama chat API and then
best-effort extracts a JSON object from the response
(`app/providers/ai/utils.py::extract_json`) even if the model wraps it in
prose or a markdown fence.

CPU-only inference is slow (single-digit tokens/sec for a ~8B model is
normal) — this is a hardware constraint, not a bug. For faster iteration
during development, use a smaller model or switch to Groq.

## Groq (free tier)

```env
AI_PROVIDER=groq
GROQ_API_KEY=your-key
GROQ_MODEL=openai/gpt-oss-120b
```

Get a key at [console.groq.com](https://console.groq.com). Groq's available
model list changes over time — check `GET https://api.groq.com/openai/v1/models`
with your key if `GROQ_MODEL`'s default stops working, and update it.

## Gemini

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.6-flash
```

Get a key at [aistudio.google.com](https://aistudio.google.com/apikey). Note
the free tier can be very restrictive per-model — e.g. `gemini-3.6-flash`
was observed capped at 20 requests/**day** (a `RESOURCE_EXHAUSTED` /
`GenerateRequestsPerDayPerProjectPerModel-FreeTier` quota, not a per-minute
one — waiting doesn't help until the daily window resets), which makes it a
poor sole/primary provider for anything that makes more than a handful of
calls a day. See "Chaining providers" below for a way to use it without that
becoming a hard limit on the whole app. Gemini's available model list also
changes over time — check
`GET https://generativelanguage.googleapis.com/v1beta/models?key=...` if
`GEMINI_MODEL`'s default stops working.

## Cerebras (OpenAI-chat-compatible)

```env
AI_PROVIDER=cerebras
CEREBRAS_API_KEY=your-key
CEREBRAS_MODEL=gpt-oss-120b
```

Get a key at [cloud.cerebras.ai](https://cloud.cerebras.ai). Check
`GET https://api.cerebras.ai/v1/models` with your key for the current model
list — an account needs billing configured before `/chat/completions` will
actually serve requests even if `/models` responds; a `payment_required`
error means that, not a code problem.

## OpenRouter (OpenAI-chat-compatible, has genuinely free models)

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=minimax/minimax-m3:free
```

Get a key at [openrouter.ai](https://openrouter.ai) (Keys page). Filter
[openrouter.ai/models](https://openrouter.ai/models) to `:free` for the
current free-model list — it changes over time, and a `:free` model routes
through a shared upstream community pool that can itself be rate-limited
independently of your own key (`upstream_429` errors with a `Retry-After`
header, which `request_with_retry` honors) — this is a genuinely separate
quota from Groq/Cerebras/Gemini, not the same limit under another name.

## Chaining providers with an explicit priority order

```env
AI_PROVIDER=chain
# uses whichever of these are filled in, in this order:
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434   # local-dev only — see note below
OLLAMA_MODEL=qwen3:8b
```

`AI_PROVIDER=chain` selects `ChainAIProvider([Groq, OpenRouter, Cerebras,
Gemini, Ollama])` (`app/providers/ai/factory.py`) — every `AIProvider` call
tries each configured provider in order and moves to the next on any
`AIProviderError` (HTTP error, rate limit, quota exhaustion, timeout) or if
a tier is simply unconfigured, without the caller needing to know more than
one provider is involved. `app/providers/ai/utils.py::request_with_retry`
also gives each individual tier a short retry-with-backoff on a 429 before
giving up on it — useful for genuine per-minute rate limits, though it can't
help a per-*day* quota like Gemini's (see above). Once a tier fails, it's
skipped (not re-attempted) for 60s so a bulk operation (a discovery agent
can make hundreds of calls) doesn't re-retry an already-known-bad tier on
every single call — see the cooldown note in `chain_provider.py`.

**Ollama is a local-dev convenience in this chain, not a real production
fallback** — on a hosted deployment (Render, etc.) there's no local Ollama
daemon for the app to reach, so that tier will simply fail there too. In
production the chain is only as deep as however many of the cloud tiers
above are actually configured and healthy.

## Any OpenAI-compatible endpoint

```env
AI_PROVIDER=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=https://your-endpoint/v1
OPENAI_COMPATIBLE_API_KEY=...
OPENAI_COMPATIBLE_MODEL=...
```

Works with vLLM, llama.cpp's server, together.ai, OpenAI itself, or anything
else that speaks the `/chat/completions` API with `response_format:
{"type": "json_object"}` support.

## Adding a new provider

Implement `AIProvider` (`app/providers/ai/base.py`) — `configured()`,
`generate_json()`, `generate_text()` — and register it in
`app/providers/ai/factory.py::build_ai_provider`. No other file needs to
change; every agent already goes through the factory.

## Cost control

Per the product's design principle of using deterministic logic before AI
(see `app/agents/scoring.py` and `app/research/extractors.py`): company/
opportunity/investor-match scoring, trigger detection, and content-hash-based
competitor-change detection are all plain Python — the LLM is only called
where genuine language understanding or generation is needed (product
understanding, ICP generation, evidence extraction from fetched page text,
content drafting, outreach drafting). Every AI call is logged to `ai_runs`
with token counts and latency for cost visibility.
