"""Outreach Agent (§25) — drafts a personalized, evidence-grounded outreach message. Never sends anything."""
from app.agents.base import BaseAgent
from app.db.models.company import Company, CompanyTrigger
from app.db.models.product import Product

SCHEMA_HINT = """{
  "message": "string — short personalized outreach message",
  "why_contacting": "string",
  "relevant_observation": "string",
  "value_proposition": "string",
  "cta": "string — low-friction call to action"
}"""

SYSTEM_PROMPT = """You draft short, genuinely personalized outreach messages. Structure:
why you're reaching out, a specific relevant observation (grounded ONLY in the evidence
given — never invent a detail about the company), a concise value proposition, and a
low-friction call to action. Avoid fake familiarity, hype, or mass-blast language. This
is a DRAFT for human review before sending — never claim it has already been sent."""


class OutreachAgent(BaseAgent):
    name = "outreach_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]  # explicitly NOT send_email / publish_post

    def draft_message(self, *, product: Product, company: Company, trigger: CompanyTrigger | None) -> dict | None:
        trigger_text = (
            f"Trigger: {trigger.description} (why it matters: {trigger.why_it_matters})"
            if trigger
            else "No specific trigger identified — base the message on general ICP fit."
        )
        user_prompt = (
            f"Product: {product.name} — {product.description}\nCTA preference: {product.cta}\n\n"
            f"Target company: {company.name} ({company.industry}, {company.country})\n"
            f"Potential pain (evidence-based hypothesis): {company.potential_pain}\n"
            f"{trigger_text}\n"
        )
        return self.call_ai_json(
            workspace_id=product.workspace_id,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_hint=SCHEMA_HINT,
            input_summary=f"outreach draft for company={company.id}",
        )
