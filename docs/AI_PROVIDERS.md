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
