"""
Brand Setup Agent. Drafts BrandBrain + ProductTruth from the product's own
founder-provided description/category — without this, a founder has to
hand-write ~19 text fields across two separate settings screens before
content generation (`content_agent.py`) or the quality gate's fabrication
checks (`content_quality_gate.py`, `product_truth_validator.py`) have any
real grounding. Mirrors icp_agent.py's shape exactly: one AI call, strict
anti-fabrication instructions, HYPOTHESES the founder reviews/edits rather
than final copy.
"""
from app.agents.base import BaseAgent
from app.db.models.product import Product, ProductProfile

SCHEMA_HINT = """{
  "brand_brain": {
    "voice": "string — one phrase describing how the brand sounds, e.g. 'direct, technical, no hype'",
    "tone": "string — one phrase, e.g. 'confident but not salesy'",
    "positioning": "string — one or two sentences, based only on the product description",
    "key_messages": ["string — 3-5 short, specific messages a reader should take away"],
    "words_to_use": ["string — 5-8 words/phrases that fit the product's actual positioning"],
    "words_to_avoid": ["string — 5-8 generic SaaS-marketing words/phrases that would undercut credibility here, e.g. 'revolutionary', 'game-changing', 'synergy'"],
    "claims": ["string — ONLY claims explicitly supported by the product description, never invented"],
    "founder_story": "string — empty, this is founder-only content the AI cannot know"
  },
  "product_truth": {
    "definition": "string — one sentence, what the product IS",
    "target_customer": "string — based only on the description/category given",
    "problem": "string — the problem it solves, based only on the description",
    "solution": "string — how it solves that problem, based only on the description",
    "core_features": ["string — features explicitly stated in the description"],
    "positioning": "string",
    "approved_claims": ["string — ONLY claims explicitly supported by the description"],
    "forbidden_claims": ["string — plausible-sounding claims a marketer might reach for that are NOT supported by the description, e.g. specific customer counts, uptime percentages, or compliance certifications never mentioned"],
    "brand_voice": "string — same as brand_brain.voice"
  }
}"""

SYSTEM_PROMPT = """You draft a founder's Brand Brain and Product Truth STRICTLY from the product
description/category/ICP context given — never invent customer counts, certifications,
integrations, metrics, or claims not explicitly present in the source text. This is
explicitly a first-draft HYPOTHESIS for a founder to review and edit, not final
brand copy — keep it grounded and specific to what's actually stated rather than
generic SaaS marketing language. claims/approved_claims must stay empty or minimal if
the description doesn't give you much to work with — never pad with invented value
props. forbidden_claims should name the specific unsupported claims a marketer would
be tempted to reach for, given the category (e.g. a compliance certification, an
uptime SLA, a customer count) that this description does NOT state."""


class BrandSetupAgent(BaseAgent):
    name = "brand_setup_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]

    def generate(self, product: Product, profile: ProductProfile | None) -> dict | None:
        user_prompt = (
            f"Product: {product.name}\n"
            f"Category: {(profile.product_category if profile else product.category)}\n"
            f"Description (founder-provided): {product.description}\n"
            f"Primary problem: {(profile.primary_problem if profile else '')}\n"
            f"Primary buyer: {(profile.primary_buyer if profile else '')}\n"
            f"Use cases: {(profile.use_cases if profile else [])}\n"
            f"Differentiators (founder-provided): {product.differentiators}\n"
            f"Brand voice hint (founder-provided, may be empty): {product.brand_voice}\n"
        )
        return self.call_ai_json(
            workspace_id=product.workspace_id,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_hint=SCHEMA_HINT,
            input_summary=f"brand_setup_generation for product={product.id}",
        )
