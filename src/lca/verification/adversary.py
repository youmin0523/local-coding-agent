"""An adversarial reviewer — the hidden 'prosecution' in the verification debate.

Where the lens judges *evaluate* an answer, the adversary actively tries to *break*
it: find the single strongest concrete error, wrong assumption, missing edge case,
or counterexample. An answer that cannot survive prosecution must not pass on judge
opinion alone — its objection becomes the precise thing the self-repair pass fixes,
so the flow is attack → defend (repair) → re-verify → deliver. This is structured
adversarial verification, not open-ended multi-agent debate (which underperforms a
single model at equal compute); the win comes from grounding, not from more chatter.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lca.core.messages import Message
from lca.providers.base import ChatRequest, LLMProvider

# The adversary says exactly this when it genuinely cannot break the answer.
_SOUND = "SOUND"


@runtime_checkable
class Adversary(Protocol):
    async def review(self, task: str, answer: str) -> str | None: ...


class LLMAdversary:
    """Prompts the model to refute an answer; returns the objection, or None if sound."""

    def __init__(self, provider: LLMProvider, model: str) -> None:
        self._provider = provider
        self._model = model

    async def review(self, task: str, answer: str) -> str | None:
        system = (
            "You are a relentless adversarial reviewer. Your job is to BREAK the proposed "
            "answer to the task: find the single strongest concrete flaw — a wrong result, a "
            "false assumption, a missing edge case, an unhandled error, or a counterexample. "
            "Be specific and technical; name the exact flaw and (if code) the input that breaks "
            f"it. If after genuine effort the answer is correct and complete, reply with exactly "
            f"'{_SOUND}'. Otherwise reply with ONLY the one most important flaw, in one sentence."
        )
        user = f"TASK:\n{task}\n\nPROPOSED ANSWER:\n{answer}"
        req = ChatRequest(
            messages=[Message.system(system), Message.user(user)],
            model=self._model,
            temperature=0.0,
            max_tokens=200,
        )
        parts: list[str] = []
        async for chunk in self._provider.chat_stream(req):
            if chunk.delta_text:
                parts.append(chunk.delta_text)
        objection = "".join(parts).strip()
        if not objection or objection.upper().startswith(_SOUND):
            return None
        return objection[:300]
