"""Multi-pass verification: diverse-lens judges, a combining gate, best-of-N
consensus, and the `Verifier` interface the agent uses to deliver-or-abstain."""

from lca.verification.consensus import select_by_consensus
from lca.verification.gate import VerificationGate, Verifier, build_llm_gate
from lca.verification.judges import LENSES, Judge, LLMJudge
from lca.verification.models import JudgeVote, Verdict

__all__ = [
    "LENSES",
    "Judge",
    "JudgeVote",
    "LLMJudge",
    "Verdict",
    "VerificationGate",
    "Verifier",
    "build_llm_gate",
    "select_by_consensus",
]
