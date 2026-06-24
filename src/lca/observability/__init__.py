"""Observability: structured logging (and later, tracing + metrics)."""

from lca.observability.logging import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
