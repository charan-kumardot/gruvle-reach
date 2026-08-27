"""Content Agent (§21-22) — generates channel-specific drafts from a core idea, always grounded in Brand Brain."""
from app.agents.base import BaseAgent
from app.db.models.product import BrandBrain

SCHEMA_HINT = """{
  "variants": [
    {"channel": "linkedin", "body": "string"},
    {"channel": "x", "body": "string"},
    {"channel": "instagram", "body": "string"},
    {"channel": "blog", "body": "string (outline, not full post)"},
    {"channel": "newsletter", "body": "string"},
    {"channel": "reddit", "body": "string (discussion angle, not a sales pitch)"}
  ]
}"""

SYSTEM_PROMPT = """You are a founder-voice content writer. Repurpose the given core idea into
platform-native drafts. Follow the brand voice/tone/positioning strictly. Use the
provided words-to-use, avoid the words-to-avoid, and only reference the given proof
points/claims — never invent statistics, customer counts, or claims not supplied.
Reddit content must read as a genuine discussion contribution, not a promotional pitch."""


class ContentAgent(BaseAgent):
    name = "content_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]

    def generate_variants(self, *, idea: str, brand: BrandBrain | None, channels: list[str]) -> dict | None:
        brand_context = (
            f"Voice: {brand.voice}\nTone: {brand.tone}\nPositioning: {brand.positioning}\n"
            f"Key messages: {brand.key_messages}\nWords to use: {brand.words_to_use}\n"
            f"Words to avoid: {brand.words_to_avoid}\nClaims (only use these): {brand.claims}\n"
            f"Proof points: {brand.proof_points}\nFounder story: {brand.founder_story}\n"
            if brand
            else "No brand brain configured yet — use a neutral, professional, founder-authentic tone."
        )
        user_prompt = f"Core idea: {idea}\n\nBrand context:\n{brand_context}\n\nGenerate drafts for channels: {channels}"
        return self.call_ai_json(
            workspace_id=brand.workspace_id if brand else None,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_hint=SCHEMA_HINT,
            input_summary=f"content generation: {idea[:120]}",
        )
