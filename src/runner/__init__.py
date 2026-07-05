"""Run orchestration (MS-1.5): runner.run(), run-id allocation, dataset gate."""

from src.runner.run import (
    DEFAULT_RUNS_DIR,
    DatasetGateError,
    RunResult,
    allocate_run_id,
    run,
)

__all__ = [
    "DEFAULT_RUNS_DIR",
    "DatasetGateError",
    "RunResult",
    "allocate_run_id",
    "run",
]
