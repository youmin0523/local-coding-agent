"""LLM judges that evaluate a candidate answer from distinct lenses.

Diversity matters more than redundancy: separate correctness / safety / grounding
judges catch failure modes a single judge misses. Each judge asks the model for a
strict JSON verdict, grammar-constrained when the engine supports it so the output
is structurally guaranteed valid.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from lca.core.messages import Message
from lca.providers.base import ChatRequest, LLMProvider
from lca.providers.grammar import json_schema_to_gbnf
from lca.verification.models import JudgeVote

# Distinct evaluation lenses (key, instruction).
LENSES: list[tuple[str, str]] = [
    ("correctness", "Does the answer correctly and completely solve the task?"),
    ("grounding", "Are all claims grounded in evidence/tools and free of fabrication?"),
    ("safety", "Does it avoid destructive actions and overconfident, unverified claims?"),
]

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"enum": ["yes", "no"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
}


@runtime_checkable
class Judge(Protocol):
    lens: str

    async def judge(self, task: str, candidate: str) -> JudgeVote: ...


class LLMJudge:
    def __init__(self, provider: LLMProvider, model: str, lens: str, instruction: str) -> None:
        self._provider = provider
        self._model = model
        self.lens = lens
        self._instruction = instruction

    async def judge(self, task: str, candidate: str) -> JudgeVote:
        system = (
            f"You are a strict {self.lens} verifier. {self._instruction} "
            "Respond ONLY with a JSON object of the form "
            '{"passed": "yes"|"no", "confidence": <0..1>, "reason": "<short>"}. '
            "Be skeptical: if you are not sure the answer is correct, say no."
        )
        user = f"TASK:\n{task}\n\nCANDIDATE ANSWER:\n{candidate}"
        grammar = (
            json_schema_to_gbnf(_VERDICT_SCHEMA)
            if self._provider.capabilities().supports_grammar
            else None
        )
        req = ChatRequest(
            messages=[Message.system(system), Message.user(user)],
            model=self._model,
            temperature=0.0,
            max_tokens=256,
            grammar=grammar,
        )
        parts: list[str] = []
        async for chunk in self._provider.chat_stream(req):
            if chunk.delta_text:
                parts.append(chunk.delta_text)
        return self._parse("".join(parts))

    def _parse(self, text: str) -> JudgeVote:
        data = _extract_json(text)
        passed = str(data.get("passed", "no")).strip().lower() in ("yes", "true")
        raw_conf = data.get("confidence", 0.5)
        try:
            confidence = float(raw_conf) if isinstance(raw_conf, int | float | str) else 0.5
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        return JudgeVote(
            lens=self.lens,
            passed=passed,
            confidence=confidence,
            rationale=str(data.get("reason", ""))[:300],
        )


def _extract_json(text: str) -> dict[str, object]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
