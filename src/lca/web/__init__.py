"""Web UI adapter (FastAPI + SSE). Depends only on the agent core/assembly."""

from lca.web.approver import WebApprover
from lca.web.server import ConversationManager, create_app

__all__ = ["ConversationManager", "WebApprover", "create_app"]
