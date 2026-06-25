"""`lca doctor` — verify the machine and engine before trusting anything above.

The #1 failure mode on this hardware is a Blackwell/CUDA mismatch silently
falling back to CPU (or an iGPU grabbing the workload), which makes everything
*appear* to work while running 5-10x too slow. Doctor surfaces that early:

* probes the NVIDIA GPU (name, VRAM total/free, driver) via ``nvidia-smi``;
* warns if a discrete RTX GPU isn't the one in use (hybrid-graphics footgun);
* checks the engine endpoint is reachable, which models it serves, and the real
  context window — flagging when it exceeds the safe 8GB budget.

It deliberately does no app work; it only reports, so it is safe to run anytime.
"""

from __future__ import annotations

import shutil
import subprocess

from pydantic import BaseModel, Field

from lca.config.settings import Settings, get_settings
from lca.providers.base import LLMProvider, ProviderHealth
from lca.providers.registry import build_provider


class GpuInfo(BaseModel):
    name: str
    vram_total_mb: int | None = None
    vram_free_mb: int | None = None
    driver_version: str = ""


class DoctorReport(BaseModel):
    gpus: list[GpuInfo] = Field(default_factory=list)
    nvidia_smi_found: bool = True
    discrete_gpu_present: bool = False
    engine: ProviderHealth = Field(default_factory=lambda: ProviderHealth(reachable=False))
    context_budget: int = 0
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.discrete_gpu_present and self.engine.reachable


def probe_gpus() -> tuple[list[GpuInfo], bool]:
    """Return (gpus, nvidia_smi_found) by parsing ``nvidia-smi`` CSV output."""
    if shutil.which("nvidia-smi") is None:
        return [], False
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return [], True
    gpus: list[GpuInfo] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        gpus.append(
            GpuInfo(
                name=parts[0],
                vram_total_mb=_to_int(parts[1]),
                vram_free_mb=_to_int(parts[2]),
                driver_version=parts[3],
            )
        )
    return gpus, True


def _to_int(value: str) -> int | None:
    try:
        return int(float(value))
    except ValueError:
        return None


async def run_doctor(
    settings: Settings | None = None, provider: LLMProvider | None = None
) -> DoctorReport:
    settings = settings or get_settings()
    provider = provider or build_provider(settings)

    gpus, smi_found = probe_gpus()
    report = DoctorReport(gpus=gpus, nvidia_smi_found=smi_found)

    discrete = [g for g in gpus if _is_discrete(g.name)]
    report.discrete_gpu_present = bool(discrete)

    if not smi_found:
        report.warnings.append(
            "nvidia-smi not found on PATH — cannot confirm the discrete GPU is active."
        )
    elif not discrete:
        report.warnings.append(
            "No discrete NVIDIA GPU detected by nvidia-smi. If you have an RTX card, the "
            "iGPU may be selected — set CUDA_VISIBLE_DEVICES=0 and the Windows graphics "
            "preference to the high-performance NVIDIA GPU."
        )
    else:
        g = discrete[0]
        if g.vram_total_mb and g.vram_total_mb < 7000:
            report.warnings.append(
                f"Discrete GPU reports only {g.vram_total_mb} MB VRAM — unusually low; "
                "confirm nvidia-smi is reading the RTX card and not an integrated adapter."
            )
        report.notes.append(f"Discrete GPU: {g.name} ({g.vram_total_mb} MB total).")

    if len(gpus) > 1:
        report.notes.append(
            "Multiple GPUs present (hybrid graphics). Ensure the engine targets the RTX card."
        )

    report.engine = await provider.health()
    if not report.engine.reachable:
        report.warnings.append(
            f"Engine endpoint {settings.llm.base_url} is not reachable. Start llama-server / "
            "LM Studio (see docs/runbook-gpu.md), then re-run `lca doctor`."
        )
    else:
        report.notes.append(
            f"Engine reachable; models: {', '.join(report.engine.models) or '(none reported)'}."
        )
        # Catch the common footgun: configured model ids the engine doesn't actually serve.
        served = report.engine.models
        active = (
            settings.llm.brain_model if settings.profile == "quality" else settings.llm.fast_model
        )
        if served and not any(active in s or s in active for s in served):
            report.warnings.append(
                f"Active model '{active}' (profile={settings.profile}) is not served by the "
                f"engine. Available: {', '.join(served)}. Set LCA_LLM__{'BRAIN' if settings.profile == 'quality' else 'FAST'}_MODEL to match."
            )

    report.context_budget = settings.llm.max_context_tokens
    n_ctx = report.engine.context_window
    if n_ctx is not None and n_ctx > 0:
        report.notes.append(f"Engine context window: {n_ctx} tokens.")
        if n_ctx > 24_576:
            report.warnings.append(
                f"Engine context window ({n_ctx}) is large for an 8GB card; KV-cache may "
                "exhaust VRAM. Consider relaunching with a smaller -c value (8-16K)."
            )
    return report


def _is_discrete(name: str) -> bool:
    lowered = name.lower()
    markers = ("rtx", "gtx", "geforce", "quadro", "tesla", "a100", "h100")
    return any(tag in lowered for tag in markers)
