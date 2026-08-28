"""
Deterministic risk classification (visibility spec §10). No AI call — a
file path either matches a protected pattern or a critical-path heuristic,
or it doesn't. CRITICAL is a hard block regardless of mode/approval,
enforced again at execution time in app/actions/git_executor.py — this
function is the single source of truth both places call.
"""
import fnmatch

from app.db.models.enums import RiskLevel

_CRITICAL_PATH_PATTERNS = [
    "*.env*", "*secret*", "*credential*", "*.pem", "*.key",
    "*auth*", "*billing*", "*payment*", "*/security/*",
    "*middleware*", "*proxy.ts", "*proxy.js",
    "*supabase*config*", "*database*config*", "*.github/workflows/*",
    "*render.yaml", "*vercel.json", "*docker-compose*", "Dockerfile*",
]

_HIGH_RISK_PATH_PATTERNS = [
    "*hero*", "*pricing*", "*nav*", "*header*", "*footer*",
    "*layout*", "*routing*", "*route*",
]

_LOW_RISK_PATH_PATTERNS = [
    "*meta*", "*seo*", "*sitemap*", "*robots.txt", "*schema*",
    "*alt*", "*og-image*", "*manifest.json",
]


def classify_risk(*, file_path: str, protected_patterns: list[str]) -> tuple[RiskLevel, str]:
    """Returns (risk_level, reason). Order matters: protected paths and
    critical heuristics always win, even if the path also looks low-risk."""
    path_lower = file_path.lower()

    for pattern in protected_patterns:
        if fnmatch.fnmatch(path_lower, pattern.lower()) or pattern.lower() in path_lower:
            return RiskLevel.CRITICAL, f"Path matches a protected pattern: {pattern}"

    for pattern in _CRITICAL_PATH_PATTERNS:
        if fnmatch.fnmatch(path_lower, pattern):
            return RiskLevel.CRITICAL, f"Path matches a critical-system pattern: {pattern}"

    for pattern in _HIGH_RISK_PATH_PATTERNS:
        if fnmatch.fnmatch(path_lower, pattern):
            return RiskLevel.HIGH, f"Path touches a high-risk UI area: {pattern}"

    for pattern in _LOW_RISK_PATH_PATTERNS:
        if fnmatch.fnmatch(path_lower, pattern):
            return RiskLevel.LOW, f"Path is metadata/SEO-only: {pattern}"

    return RiskLevel.MEDIUM, "No specific pattern matched — treated as supporting content by default"


def is_auto_prepareable(risk_level: RiskLevel) -> bool:
    """Only LOW and MEDIUM risk changes may ever reach branch/PR creation
    automatically (§10, §33) — HIGH and CRITICAL always require the founder
    to draft the change themselves outside Reach, or Reach only ever
    analyzes/proposes for them, never prepares a PR."""
    return risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
