"""ICP Agent (§9)."""
from app.agents.base import BaseAgent
from app.db.models.product import Product, ProductProfile

SCHEMA_HINT = """{
  "icps": [
    {
      "name": "string, e.g. 'US B2B SaaS, 20-200 employees, using Stripe + OpenAI'",
      "criteria": {
        "industries": ["string"],
        "company_size_min": 0,
        "company_size_max": 0,
        "geographies": ["string"],
        "technology_stack": ["string"],
        "funding_stages": ["string"],
        "business_models": ["string"]
      },
      "factors": {
        "pain": 0,
        "ability_to_pay": 0,
        "reachability": 0,
        "product_fit": 0,
        "urgency": 0,
        "market_size": 0,
        "competition": 0
      },
      "score": 0,
      "rationale": "string"
    }
  ]
}"""

SYSTEM_PROMPT = """You are an ICP (Ideal Customer Profile) strategist. Given a product's understanding,
generate 2-4 GRANULAR ICP hypotheses — never something as vague as "SaaS founders".
Each ICP must specify concrete industries, company size range, geography, technology
stack signals, funding stage, and business model.

Score each of the 7 factors (pain, ability_to_pay, reachability, product_fit, urgency,
market_size, competition) from 0-100, then compute an overall score (0-100) as their
average. These are HYPOTHESES for the founder to validate and confirm — say so in the
rationale, do not present them as verified facts."""


class ICPAgent(BaseAgent):
    name = "icp_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]

    def run(self, product: Product, profile: ProductProfile | None) -> dict | None:
        user_prompt = (
            f"Product: {product.name} — {product.description}\n"
            f"Category: {(profile.product_category if profile else product.category)}\n"
            f"Primary problem: {(profile.primary_problem if profile else '')}\n"
            f"Primary buyer: {(profile.primary_buyer if profile else '')}\n"
            f"Target industries (hypothesized): {(profile.target_industries if profile else [])}\n"
            f"Use cases: {(profile.use_cases if profile else [])}\n"
            f"Founder-provided target markets: {product.target_markets}\n"
            f"Founder-provided target countries: {product.target_countries}\n"
        )
        return self.call_ai_json(
            workspace_id=product.workspace_id,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_hint=SCHEMA_HINT,
            input_summary=f"icp_generation for product={product.id}",
        )
