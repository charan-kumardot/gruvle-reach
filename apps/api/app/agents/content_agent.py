"""Content Agent (§21-22, §4). Generates channel-specific drafts from a core
idea, always grounded in Brand Brain. Also the spec's "RepurposingAgent"
(§23) — generate_repurposed_variants reuses the same brand-grounded call
with source_idea_id lineage set by the caller, not a separate decision
engine."""
from app.agents.base import BaseAgent
from app.db.models.product import BrandBrain

SCHEMA_HINT = """{
  "variants": [
    {"channel": "linkedin", "body": "string", "cta": "string"},
    {"channel": "x", "body": "string", "cta": "string"},
    {"channel": "instagram", "body": "string", "cta": "string"},
    {"channel": "blog", "body": "string (outline, not full post)", "cta": "string"},
    {"channel": "newsletter", "body": "string", "cta": "string"},
    {"channel": "reddit", "body": "string (discussion angle, not a sales pitch)", "cta": "string"}
  ]
}"""

# Per-platform format guidance (§4) — the model is told each channel's
# culture/limits explicitly rather than left to guess, and is instructed
# not to just reflow the same paragraph everywhere (§4: "do not generate
# identical content for every platform").
_PLATFORM_RULES = """Per-platform rules — adapt the IDEA to each platform's own culture and
constraints, do not generate the same text reflowed for every channel:
- linkedin: a hook line, a short body (under 3000 chars), a clear CTA. Hashtags only if genuinely useful, never more than 3.
- x: under 280 characters. If the idea needs more room, write it as a short thread outline in the body (numbered points), not a single long paragraph.
- instagram: a caption plus a one-line note on what the visual/carousel should show, written as part of the body. No walls of hashtags.
- blog: an outline (headings + one-line summaries per section), not a full draft.
- newsletter: a short, personal-voice section suitable for inclusion in a digest, not a press release.
- reddit: must read as a genuine discussion contribution or answer to a real question in the community — never a pitch. No CTA beyond an honest, low-pressure mention if directly relevant.
- facebook: conversational, slightly longer than X, page-post style.
Each variant's "cta" field should be a short call-to-action phrase appropriate to the platform (may be empty for reddit)."""

SYSTEM_PROMPT = f"""You are a founder-voice content writer. Repurpose the given core idea into
platform-native drafts. Follow the brand voice/tone/positioning strictly. Use the
provided words-to-use, avoid the words-to-avoid, and only reference the given proof
points/claims — never invent statistics, customer counts, features, testimonials,
partnerships, funding, or security/compliance certifications not supplied.

{_PLATFORM_RULES}"""


def _brand_context(brand: BrandBrain | None) -> str:
    return (
        f"Voice: {brand.voice}\nTone: {brand.tone}\nPositioning: {brand.positioning}\n"
        f"Key messages: {brand.key_messages}\nWords to use: {brand.words_to_use}\n"
        f"Words to avoid: {brand.words_to_avoid}\nClaims (only use these): {brand.claims}\n"
        f"Proof points: {brand.proof_points}\nFounder story: {brand.founder_story}\n"
        if brand
        else "No brand brain configured yet — use a neutral, professional, founder-authentic tone."
    )


class ContentAgent(BaseAgent):
    name = "content_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]

    def generate_variants(
        self, *, idea: str, brand: BrandBrain | None, channels: list[str], cta_hint: str = ""
    ) -> dict | None:
        cta_line = f"\n\nPreferred CTA intent for this content: {cta_hint}" if cta_hint else ""
        user_prompt = (
            f"Core idea: {idea}\n\nBrand context:\n{_brand_context(brand)}\n\n"
            f"Generate drafts for channels: {channels}{cta_line}"
        )
        return self.call_ai_json(
            workspace_id=brand.workspace_id if brand else None,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_hint=SCHEMA_HINT,
            input_summary=f"content generation: {idea[:120]}",
        )

    def generate_repurposed_variants(
        self, *, source_idea: str, brand: BrandBrain | None, channels: list[str], cta_hint: str = ""
    ) -> dict | None:
        """One high-value idea -> multiple platform-adapted assets (§23). Same
        call as generate_variants — repurposing is a lineage decision the
        caller encodes via Content.source_idea_id, not a different prompt."""
        return self.generate_variants(idea=source_idea, brand=brand, channels=channels, cta_hint=cta_hint)
