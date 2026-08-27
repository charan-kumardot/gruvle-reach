"""
Deterministic, rule-based signal extraction from fetched page text (§79:
"use deterministic logic before AI"). These heuristics are intentionally
conservative — they flag *candidate* signals with a confidence score; the
research agent decides whether to also ask the LLM to characterize them, and
everything downstream is stored as HYPOTHESIS unless a human confirms it.
"""
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

FUNDING_PATTERNS = [
    re.compile(r"\braised\s+\$[\d.,]+\s*(?:million|billion|M|B)\b", re.IGNORECASE),
    re.compile(r"\bseries\s+[a-e]\b.{0,40}\bfunding\b", re.IGNORECASE),
    re.compile(r"\b(?:seed|pre-seed)\s+round\b", re.IGNORECASE),
]

HIRING_PATTERNS = [
    re.compile(r"\bwe(?:'re| are) hiring\b", re.IGNORECASE),
    re.compile(r"\bjoin our team\b", re.IGNORECASE),
    re.compile(r"\bopen positions?\b", re.IGNORECASE),
]

LAUNCH_PATTERNS = [
    re.compile(r"\bwe(?:'re| are) (?:excited|thrilled) to (?:announce|launch)\b", re.IGNORECASE),
    re.compile(r"\bintroducing\b", re.IGNORECASE),
    re.compile(r"\bnow (?:available|live)\b", re.IGNORECASE),
]

TECH_KEYWORDS = [
    "stripe", "openai", "anthropic", "aws", "gcp", "azure", "kubernetes", "docker",
    "graphql", "rest api", "webhook", "postgres", "snowflake", "segment", "twilio",
]


@dataclass
class ExtractedSignal:
    signal_type: str
    description: str
    confidence: float
    snippet: str


def strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def _snippet_around(text: str, match: re.Match, radius: int = 160) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip()


def extract_signals(text: str) -> list[ExtractedSignal]:
    signals: list[ExtractedSignal] = []

    for pattern in FUNDING_PATTERNS:
        for match in pattern.finditer(text):
            signals.append(ExtractedSignal("funding", "Possible funding announcement", 0.6, _snippet_around(text, match)))

    for pattern in HIRING_PATTERNS:
        for match in pattern.finditer(text):
            signals.append(ExtractedSignal("hiring", "Possible hiring/expansion signal", 0.5, _snippet_around(text, match)))

    for pattern in LAUNCH_PATTERNS:
        for match in pattern.finditer(text):
            signals.append(ExtractedSignal("product_launch", "Possible product/feature launch", 0.5, _snippet_around(text, match)))

    lowered = text.lower()
    for keyword in TECH_KEYWORDS:
        if keyword in lowered:
            idx = lowered.index(keyword)
            snippet = text[max(0, idx - 100) : idx + 100]
            signals.append(ExtractedSignal("technology_adoption", f"Mentions '{keyword}'", 0.4, snippet.strip()))

    return signals
