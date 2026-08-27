"""
Base class for all agents (§68-70). An agent declares the tools/actions it's
allowed to use and produces recommendations only — it never calls a
provider adapter that sends/publishes anything external. That boundary is
enforced structurally: agents only have access to AIProvider, SearchProvider,
the SSRF-safe fetcher, and the database session. Sending/publishing lives
exclusively in app/actions/executor.py, gated by human approval.
"""
import time
import uuid
from typing import ClassVar

from sqlalchemy.orm import Session

from app.db.models.ai_run import AIRun
from app.providers.ai.base import AIGenerationResult, AIProvider, AIProviderError


class BaseAgent:
    name: ClassVar[str] = "base_agent"
    allowed_tools: ClassVar[list[str]] = []
    allowed_actions: ClassVar[list[str]] = []  # e.g. "database_write" — never "send_email", "publish_post"

    def __init__(self, db: Session, ai_provider: AIProvider):
        self.db = db
        self.ai = ai_provider

    def call_ai_json(
        self,
        *,
        workspace_id: uuid.UUID | None,
        system_prompt: str,
        user_prompt: str,
        schema_hint: str,
        input_summary: str,
    ) -> dict | None:
        started = time.perf_counter()
        try:
            result: AIGenerationResult = self.ai.generate_json(
                system_prompt=system_prompt, user_prompt=user_prompt, schema_hint=schema_hint
            )
            status = "success" if result.raw_json is not None else "invalid_schema"
            error = "" if result.raw_json is not None else "Model response did not contain parseable JSON"
        except AIProviderError as exc:
            result = None
            status = "failed"
            error = str(exc)

        self.db.add(
            AIRun(
                workspace_id=workspace_id,
                agent_name=self.name,
                provider=self.ai.name,
                model=getattr(self.ai, "_model", ""),
                input_summary=input_summary[:2000],
                output=(result.raw_json if result and result.raw_json else {}),
                status=status,
                tokens_used=result.tokens_used if result else 0,
                latency_ms=(time.perf_counter() - started) * 1000,
                error=error,
            )
        )
        self.db.flush()
        return result.raw_json if result else None
