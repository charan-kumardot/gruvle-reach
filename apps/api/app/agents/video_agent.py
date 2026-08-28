"""
Video Agent (§9-10, §41). Script generation only — the only AI call in the
video pipeline. Rendering (scenes/voiceover/captions/mp4) is deterministic
and lives in app/media/, not here, mirroring this codebase's existing
division of labor: agents own AI calls, providers/media own external-system
I/O and computation.
"""
from dataclasses import dataclass

from app.agents.base import BaseAgent
from app.db.models.product import BrandBrain
from app.db.models.visibility import ProductTruth

SCHEMA_HINT = """{
  "hook": "string — max ~12 words, must be sayable in about 3 seconds",
  "problem": "string — max ~16 words, ~4 seconds",
  "insight": "string — max ~16 words, ~4 seconds",
  "solution": "string — max ~14 words, ~4 seconds, names the product",
  "product": "string — max ~12 words, ~3 seconds, what it does in plain terms",
  "cta": "string — max ~14 words, ~4 seconds"
}"""

SYSTEM_PROMPT = """You write short-form video scripts (§10): HOOK, PROBLEM, INSIGHT, SOLUTION,
PRODUCT, CTA. Each field is a single short spoken line, not a paragraph — respect the word
limits given, they map directly to on-screen seconds. Ground every claim in the given
product facts (brand voice/claims/proof points, and product truth if given) — never
invent statistics, customer counts, features, or guarantees. Do not exaggerate ("automatically
solves X") beyond what the facts support. Plain, confident, founder-authentic tone, no hype
words."""


@dataclass
class Scene:
    key: str
    text: str
    duration_seconds: float


# Fixed per-key durations (§10 example totals ~22s) — deterministic, not
# model-decided, so render time and cost stay bounded and reproducible.
_SCENE_DURATIONS: dict[str, float] = {
    "hook": 3.0,
    "problem": 4.0,
    "insight": 4.0,
    "solution": 4.0,
    "product": 3.0,
    "cta": 4.0,
}
_SCENE_ORDER = ["hook", "problem", "insight", "solution", "product", "cta"]


class VideoAgent(BaseAgent):
    name = "video_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]

    def write_script(
        self, *, idea: str, brand: BrandBrain | None, truth: ProductTruth | None, cta_hint: str = ""
    ) -> dict | None:
        brand_context = (
            f"Voice: {brand.voice}\nClaims (only use these): {brand.claims}\nProof points: {brand.proof_points}\n"
            if brand
            else "No brand brain configured — use a neutral, professional tone and make no specific claims."
        )
        truth_context = (
            f"Definition: {truth.definition}\nProblem: {truth.problem}\nSolution: {truth.solution}\n"
            f"Core features: {truth.core_features}\nForbidden claims: {truth.forbidden_claims}\n"
            if truth
            else ""
        )
        cta_line = f"\nPreferred CTA intent: {cta_hint}" if cta_hint else ""
        user_prompt = f"Video idea/topic: {idea}\n\nBrand context:\n{brand_context}\n{truth_context}{cta_line}"
        return self.call_ai_json(
            workspace_id=brand.workspace_id if brand else None,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_hint=SCHEMA_HINT,
            input_summary=f"video script: {idea[:120]}",
        )


def compose_scenes(script: dict) -> list[Scene]:
    """Pure function, no AI — turns a script dict into a fixed-duration
    scene list. Any missing/empty key is skipped rather than rendered blank."""
    scenes = []
    for key in _SCENE_ORDER:
        text = (script.get(key) or "").strip()
        if not text:
            continue
        scenes.append(Scene(key=key, text=text, duration_seconds=_SCENE_DURATIONS[key]))
    return scenes
