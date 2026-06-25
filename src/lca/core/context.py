"""Assembles the model's prompt for a turn.

Combines the system prompt, an optional block of retrieved context (code chunks
from RAG and verified experiences from memory, added in later milestones), and the
running history, fitted under the session's token budget. A crude char-based
trimmer stands in for a tokenizer; it errs on the side of keeping recent turns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lca.core.messages import Message
from lca.core.prompts import SYSTEM_PROMPT, workspace_note
from lca.core.session import Session

# Rough chars-per-token for budgeting without a tokenizer dependency.
_CHARS_PER_TOKEN = 4


@dataclass
class RetrievedContext:
    """Grounding snippets to inject (code chunks, remembered experiences)."""

    code_snippets: list[str] = field(default_factory=list)
    experiences: list[str] = field(default_factory=list)

    def render(self) -> str:
        blocks: list[str] = []
        if self.experiences:
            joined = "\n".join(f"- {e}" for e in self.experiences)
            blocks.append(f"Relevant verified experiences and lessons from past work:\n{joined}")
        if self.code_snippets:
            joined = "\n\n".join(self.code_snippets)
            blocks.append(f"Relevant code from the workspace:\n{joined}")
        return "\n\n".join(blocks)


class ContextBuilder:
    def __init__(self, skills_note: str = "") -> None:
        # Tier-1 skill metadata (name+description) always present in the system prompt.
        self._skills_note = skills_note

    def build(
        self,
        session: Session,
        user_input: str,
        retrieved: RetrievedContext | None = None,
    ) -> list[Message]:
        system = SYSTEM_PROMPT + "\n\n" + workspace_note(str(session.workspace_root))
        if self._skills_note:
            system += "\n\n" + self._skills_note
        grounding = retrieved.render() if retrieved else ""
        if grounding:
            system += "\n\n" + grounding

        budget_chars = max(2000, session.token_budget * _CHARS_PER_TOKEN - len(system))
        kept, dropped = self._trim(session.history, budget_chars)
        if dropped:
            # Don't silently lose old turns — keep a compact summary for continuity.
            system += "\n\n" + self._summarize(dropped)

        messages: list[Message] = [Message.system(system)]
        messages.extend(kept)
        messages.append(Message.user(user_input))
        return messages

    @staticmethod
    def _trim(history: list[Message], budget_chars: int) -> tuple[list[Message], list[Message]]:
        """Split history into (kept-recent, dropped-older) under the char budget."""
        kept: list[Message] = []
        used = 0
        cutoff = 0
        for i, msg in enumerate(reversed(history)):
            size = len(msg.content or "") + sum(len(str(tc.arguments)) for tc in msg.tool_calls)
            if used + size > budget_chars and kept:
                cutoff = len(history) - i
                break
            kept.append(msg)
            used += size
        kept.reverse()
        return kept, history[:cutoff]

    @staticmethod
    def _summarize(dropped: list[Message]) -> str:
        """A cheap, LLM-free recap of earlier turns (the user's past requests)."""
        asks = [
            (m.content or "").strip().splitlines()[0][:100]
            for m in dropped
            if m.role == "user" and m.content
        ]
        if not asks:
            return ""
        recent = asks[-5:]
        lines = "\n".join(f"- {a}" for a in recent)
        return f"Earlier in this session you worked on:\n{lines}"
