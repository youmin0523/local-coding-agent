"""Web UI adapter (FastAPI + SSE). Depends only on the agent core/assembly."""

from lca.web.approver import WebApprover
from lca.web.server import RunManager, create_app

__all__ = ["RunManager", "WebApprover", "create_app"]
