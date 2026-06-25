"""Composition root: assemble a fully-wired `Agent` from configuration.

Both the CLI and the web backend build the agent the same way through here, so the
two front-ends are guaranteed to behave identically. This module may import any
domain layer but never the UI layers (it is what the UI calls, not the reverse).
"""

from __future__ import annotations

from typing import Literal

from lca.config.paths import index_db_path, memory_db_path
from lca.config.settings import Settings, get_settings
from lca.core.agent import Agent
from lca.mcp.client import MCPClientManager
from lca.mcp.servers import default_servers
from lca.memory.memory import ExperienceMemory, Memory
from lca.memory.store import MemoryStore
from lca.permissions.approver import Approver
from lca.permissions.policy import DefaultPolicy
from lca.providers.base import LLMProvider
from lca.providers.registry import build_provider, resolve_model
from lca.rag.embedder import default_embedder
from lca.rag.hybrid import HybridRetriever
from lca.rag.reranker import default_reranker
from lca.rag.retriever import Retriever
from lca.rag.store import SqliteVectorStore
from lca.skills.loader import default_skill_roots, load_skills, skills_index
from lca.tools import build_default_registry
from lca.tools.skill import UseSkillTool
from lca.verification.gate import build_llm_gate

LogicalModel = Literal["brain", "fast"]


def open_retriever() -> Retriever | None:
    """Open the on-disk code index as a retriever, if one exists."""
    db = index_db_path()
    if not db.exists():
        return None
    reranker = default_reranker(get_settings().rag_rerank)
    return HybridRetriever(SqliteVectorStore(db), default_embedder(), reranker=reranker)


def open_memory() -> Memory:
    """Open the persistent experience memory (created on first write)."""
    return ExperienceMemory(MemoryStore(memory_db_path()), default_embedder())


async def attach_mcp(agent: Agent, workspace: str) -> MCPClientManager:
    """Connect the default local MCP servers and register their tools on the agent.

    Returns the `MCPClientManager` (caller must `await .aclose()` when done). Broken
    servers are skipped, so a missing npx/uvx doesn't take the agent down.
    """
    manager = MCPClientManager()
    await manager.connect_all(default_servers(workspace), agent.registry)
    return manager


def build_agent(
    approver: Approver,
    *,
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    model_logical: LogicalModel = "brain",
    verify: bool = False,
    samples: int = 1,
    use_memory: bool = True,
    enable_web: bool = True,
) -> Agent:
    settings = settings or get_settings()
    provider = provider or build_provider(settings)
    model = resolve_model(model_logical, settings)
    retriever = open_retriever()
    memory = open_memory() if use_memory else None
    verifier = (
        build_llm_gate(provider, model, pass_threshold=settings.verify_pass_threshold)
        if verify
        else None
    )
    registry = build_default_registry(retriever, enable_web=enable_web)
    skills = load_skills(*default_skill_roots())
    if skills:
        registry.register(UseSkillTool(skills))
    return Agent(
        provider,
        registry,
        DefaultPolicy(),
        approver,
        model=model,
        retriever=retriever,
        verifier=verifier,
        memory=memory,
        samples=samples,
        max_tokens=settings.llm.max_context_tokens // 4,
        skills_note=skills_index(skills),
        response_language=settings.response_language,
    )
