"""AI output that isn't valid JSON must never crash a route or silently pass
through as if it were structured data (§45, §70)."""
from app.providers.ai.base import AIGenerationResult, AIProvider
from app.providers.ai.utils import extract_json


def test_extract_json_handles_markdown_fence():
    text = 'Sure, here is the JSON:\n```json\n{"a": 1, "b": [2, 3]}\n```\nHope that helps!'
    assert extract_json(text) == {"a": 1, "b": [2, 3]}


def test_extract_json_handles_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_returns_none_for_garbage():
    assert extract_json("I cannot help with that request.") is None


class _GarbageAIProvider(AIProvider):
    name = "garbage"

    def configured(self):
        return True

    def generate_json(self, *, system_prompt, user_prompt, schema_hint):
        return AIGenerationResult(text="not json at all", raw_json=None, provider=self.name, model="none")

    def generate_text(self, *, system_prompt, user_prompt):
        return AIGenerationResult(text="ok", raw_json=None, provider=self.name, model="none")


def test_agent_logs_invalid_schema_and_returns_none(db):
    from app.agents.base import BaseAgent

    agent = BaseAgent(db, _GarbageAIProvider())
    result = agent.call_ai_json(
        workspace_id=None, system_prompt="sys", user_prompt="user", schema_hint="{}", input_summary="test"
    )
    assert result is None
    db.rollback()
