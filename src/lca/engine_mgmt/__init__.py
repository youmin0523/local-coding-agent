"""Engine lifecycle helpers: health/GPU diagnostics (`doctor`) and launching."""

from lca.engine_mgmt.doctor import DoctorReport, GpuInfo, run_doctor

__all__ = ["DoctorReport", "GpuInfo", "run_doctor"]
