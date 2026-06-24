"""Named runtime profiles.

A profile bundles the model-selection and decoding defaults for a given way of
running the agent on this 8GB-VRAM machine:

* ``quality`` — the Qwen3-Coder-30B-A3B MoE "brain" via ``--n-cpu-moe`` offload
  (~12-15 tok/s, best reasoning).
* ``fast`` — the Qwen2.5-Coder-7B dense model, fully GPU-resident (snappy, and
  the only model we can fine-tune locally).

The difficulty router (M10) switches between brain/fast per task; a profile sets
the *default* and the ceiling.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ProfileName(StrEnum):
    QUALITY = "quality"
    FAST = "fast"


class Profile(BaseModel):
    """Decoding + model defaults for a runtime profile."""

    name: ProfileName
    default_model: str  # logical name; resolved to an engine model id via Settings
    temperature: float
    max_output_tokens: int
    # How many candidates the verification gate samples for checkable tasks.
    default_samples: int


_PROFILES: dict[ProfileName, Profile] = {
    ProfileName.QUALITY: Profile(
        name=ProfileName.QUALITY,
        default_model="brain",
        temperature=0.2,
        max_output_tokens=2048,
        default_samples=3,
    ),
    ProfileName.FAST: Profile(
        name=ProfileName.FAST,
        default_model="fast",
        temperature=0.2,
        max_output_tokens=1024,
        default_samples=1,
    ),
}


def get_profile(name: ProfileName | str) -> Profile:
    return _PROFILES[ProfileName(name)]
