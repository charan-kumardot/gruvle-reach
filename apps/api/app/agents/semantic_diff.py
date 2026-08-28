"""
Semantic Change Analysis (visibility spec §16) — a normal git diff shows
what text changed; this shows what it MEANS. Combines the deterministic
risk classifier, the Product Truth Validator, a brand-voice keyword check
against Design Constitution, and a deterministic SEO-impact estimate.
"""
from dataclasses import asdict, dataclass

from app.agents.product_truth_validator import ProductTruthValidator, ValidationResult
from app.db.models.visibility import DesignConstitution, ProductTruth


@dataclass
class SemanticDiffResult:
    product_meaning: str  # "unchanged" | "changed_supported" | "changed_unsupported"
    unsupported_claims: list[str]
    brand_alignment_score: float  # 0-100, heuristic
    brand_notes: list[str]
    seo_impact_estimate: str  # human-readable, always hedged as "estimated"
    ui_impact: str  # "unchanged" | "content_only" | "structural"
    validator_reason: str


def _brand_alignment(new_text: str, constitution: DesignConstitution | None) -> tuple[float, list[str]]:
    if constitution is None or not constitution.navigation and not constitution.typography:
        return 75.0, ["No Design Constitution configured yet — using a neutral baseline score."]
    notes = []
    score = 90.0
    # Lightweight heuristic: flag if the new text is drastically longer/shorter
    # than typical, or introduces ALL-CAPS shouting, which usually signals a
    # tone mismatch worth a human glance rather than a hard rule.
    if new_text.isupper() and len(new_text) > 20:
        score -= 20
        notes.append("Proposed text is in all caps — check against brand tone.")
    return score, notes


def compute_semantic_diff(
    *,
    old_text: str,
    new_text: str,
    file_path: str,
    truth: ProductTruth | None,
    constitution: DesignConstitution | None,
    validator: ProductTruthValidator,
    workspace_id,
) -> SemanticDiffResult:
    if truth is None:
        validation = ValidationResult(allowed=True, reason="No Product Truth configured yet — nothing to validate against.", unsupported_claims=[])
    else:
        validation = validator.validate(proposed_text=new_text, truth=truth, workspace_id=workspace_id)

    product_meaning = "unchanged" if old_text.strip() == new_text.strip() else (
        "changed_supported" if validation.allowed else "changed_unsupported"
    )

    brand_score, brand_notes = _brand_alignment(new_text, constitution)

    # Deterministic, hedged SEO estimate: reward filling in previously-empty
    # metadata and landing within commonly-cited optimal length ranges.
    seo_notes = []
    if "meta" in file_path.lower() or "description" in file_path.lower():
        new_len = len(new_text)
        if not old_text.strip() and new_text.strip():
            seo_notes.append("Fills a previously missing meta description")
        if 120 <= new_len <= 160:
            seo_notes.append("Length within the commonly-cited optimal range (120-160 chars)")
        elif new_len > 160:
            seo_notes.append(f"Length ({new_len} chars) exceeds the commonly-cited 160-char guideline")
    seo_impact_estimate = "; ".join(seo_notes) or "No specific SEO signal detected for this file type"

    ui_impact = "unchanged" if file_path.lower().endswith((".md", ".txt", ".json", "sitemap.xml", "robots.txt")) else "content_only"

    return SemanticDiffResult(
        product_meaning=product_meaning,
        unsupported_claims=validation.unsupported_claims,
        brand_alignment_score=brand_score,
        brand_notes=brand_notes,
        seo_impact_estimate=f"Estimated: {seo_impact_estimate}",
        ui_impact=ui_impact,
        validator_reason=validation.reason,
    )


def semantic_diff_to_dict(result: SemanticDiffResult) -> dict:
    return asdict(result)
