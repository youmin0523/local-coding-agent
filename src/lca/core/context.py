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
            blocks.append(f"Relevant verified experiences from past work:\n{joined}")
        if self.code_snippets:
            joined = "\n\n".join(self.code_snippets)
            blocks.append(f"Relevant code from the workspace:\n{joined}")
        return "\n\n".join(blocks)


class ContextBuilder:
    def build(
        self,
        session: Session,
        user_input: str,
        retrieved: RetrievedContext | None = None,
    ) -> list[Message]:
        system = SYSTEM_PROMPT + "\n\n" + workspace_note(str(session.workspace_root))
        grounding = retrieved.render() if retrieved else ""
        if grounding:
            system += "\n\n" + grounding

        messages: list[Message] = [Message.system(system)]
        budget_chars = max(2000, session.token_budget * _CHARS_PER_TOKEN - len(system))
        history = self._trim(session.history, budget_chars)
        messages.extend(history)
        messages.append(Message.user(user_input))
        return messages

    @staticmethod
    def _trim(history: list[Message], budget_chars: int) -> list[Message]:
        """Keep the most recent messages that fit in the budget."""
        kept: list[Message] = []
        used = 0
        for msg in reversed(history):
            size = len(msg.content or "") + sum(len(str(tc.arguments)) for tc in msg.tool_calls)
            if used + size > budget_chars and kept:
                break
            kept.append(msg)
            used += size
        kept.reverse()
        return kept
