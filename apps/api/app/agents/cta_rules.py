"""
CTA intelligence (§27). Deterministic, no AI call — same "deterministic
before AI" precedent as risk_classifier.py. The *family* of CTA (what kind
of ask) is policy, chosen here by content_type/intent; the exact wording is
still brand-voice-adapted by the LLM inside ContentAgent. Keeps CTA
selection reproducible and explainable instead of left entirely to the
model's judgment call every time.
"""

CTA_BY_INTENT: dict[str, str] = {
    "educational": "Learn more",
    "authority": "See the research",
    "social_proof": "See how teams use it",
    "product": "See how it works",
    "engagement": "Join the discussion",
    "promotional": "Get started",
}

DEFAULT_CTA = "Learn more"


def cta_for_content_type(content_type: str) -> str:
    """Returns the CTA family for a content type. Investor-facing and
    community-facing content are handled by the caller passing the right
    content_type ('social_proof'/'authority' style intents) — this stays a
    small flat lookup, not a second classification pass."""
    return CTA_BY_INTENT.get(content_type, DEFAULT_CTA)
