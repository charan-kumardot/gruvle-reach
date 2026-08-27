import json
import re


def extract_json(text: str) -> dict | None:
    """Best-effort JSON extraction from an LLM response that may wrap the
    object in markdown fences or surrounding prose."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            return None
    return None
