"""Sandboxed subprocess execution.

The pure-Python default runs commands via ``create_subprocess_exec`` (no shell)
with a hard wall-clock timeout, a scrubbed environment, a fixed working directory,
and bounded captured output. Network isolation is best-effort on Windows without a
container and is documented as such; a Docker-backed runner (stronger isolation) is
an optional power-up added later.

This is the only place the agent touches the OS to run code, so all the guards
live here rather than being sprinkled through the tools.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel

from lca.core.errors import SandboxError
from lca.observability.logging import get_logger

log = get_logger("permissions.sandbox")

_MAX_OUTPUT_CHARS = 20_000

# Environment variables kept when scrubbing; everything else is dropped so secrets
# in the parent environment don't leak into executed code.
_ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "WINDIR", "PATHEXT", "HOME", "USERPROFILE")


class SandboxResult(BaseModel):
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class SandboxRunner:
    def __init__(
        self,
        workspace_root: Path,
        *,
        timeout_s: float = 60.0,
        no_network: bool = False,
        max_output_chars: int = _MAX_OUTPUT_CHARS,
    ) -> None:
        self._root = workspace_root
        self._timeout = timeout_s
        self._no_network = no_network
        self._max_output = max_output_chars

    def _scrubbed_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = {k: os.environ[k] for k in _ENV_ALLOWLIST if k in os.environ}
        # A hint some libraries honor; not a guarantee of network isolation.
        if self._no_network:
            env["LCA_NO_NETWORK"] = "1"
        if extra:
            env.update(extra)
        return env

    async def run_command(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env_extra: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> SandboxResult:
        if not argv:
            raise SandboxError("empty command")
        workdir = (cwd or self._root).resolve()
        timeout = timeout_s if timeout_s is not None else self._timeout
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(workdir),
                env=self._scrubbed_env(env_extra),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, ValueError) as exc:
            raise SandboxError(f"failed to start {argv[0]!r}: {exc}") from exc

        timed_out = False
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            timed_out = True
            proc.kill()
            out, err = await proc.communicate()
            log.warning("sandbox.timeout", argv=argv[:3], timeout_s=timeout)

        return SandboxResult(
            exit_code=proc.returncode,
            stdout=self._truncate(out),
            stderr=self._truncate(err),
            timed_out=timed_out,
            duration_s=round(time.monotonic() - start, 3),
        )

    async def run_python(self, code: str, *, timeout_s: float | None = None) -> SandboxResult:
        """Run a Python snippet with the current interpreter in the sandbox.

        The snippet is written to a private temp directory; it runs with the
        workspace as cwd (so it can import project code) under the same timeout /
        scrubbed-env / no-network guards as any other command.
        """
        with tempfile.TemporaryDirectory(prefix="lca_exec_") as tmp:
            snippet = Path(tmp) / "snippet.py"
            snippet.write_text(code, encoding="utf-8")
            # Put the workspace on PYTHONPATH so the snippet can import the user's
            # modules (e.g. `import fib` after writing fib.py) — the script itself
            # lives in a temp dir, so cwd alone is not enough.
            return await self.run_command(
                [sys.executable, str(snippet)],
                cwd=self._root,
                timeout_s=timeout_s,
                env_extra={"PYTHONPATH": str(self._root)},
            )

    def _truncate(self, raw: bytes) -> str:
        text = raw.decode("utf-8", errors="replace")
        if len(text) > self._max_output:
            head = text[: self._max_output]
            return f"{head}\n…[truncated {len(text) - self._max_output} chars]"
        return text
