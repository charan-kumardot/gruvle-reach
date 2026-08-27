"""Product Understanding Agent (§8)."""
import uuid

from app.agents.base import BaseAgent
from app.db.models.product import Product

SCHEMA_HINT = """{
  "product_category": "string",
  "primary_problem": "string",
  "primary_buyer": "string",
  "secondary_buyers": ["string"],
  "target_industries": ["string"],
  "use_cases": ["string"],
  "competitive_categories": ["string"],
  "keywords": ["string"],
  "search_queries": ["string"]
}"""

SYSTEM_PROMPT = """You are a product-market research analyst. Given a product's public description,
infer its category, primary problem it solves, likely buyer, and target industries.

Be precise and concrete — avoid vague industry buzzwords. Every field is a
HYPOTHESIS to be validated with real research, not a verified fact; do not
claim certainty. Output search_queries as concrete, usable web search
queries a researcher could run to validate these hypotheses."""


class ProductUnderstandingAgent(BaseAgent):
    name = "product_understanding_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]

    def run(self, product: Product) -> dict | None:
        user_prompt = (
            f"Product name: {product.name}\n"
            f"Website: {product.website}\n"
            f"Description: {product.description}\n"
            f"Category (founder-provided): {product.category}\n"
            f"Target markets (founder-provided): {product.target_markets}\n"
            f"Known competitors: {product.competitors}\n"
        )
        return self.call_ai_json(
            workspace_id=product.workspace_id,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_hint=SCHEMA_HINT,
            input_summary=f"product_understanding for product={product.id}",
        )
