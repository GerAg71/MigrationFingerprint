"""Rule engine (MS-1.4): field_compare, count_balance, referential.

derived_recompute, encoding_check, sort_order_check arrive in MS-2.1.
"""

from src.rules._common import ExecutionContext
from src.rules.engine import (
    EXECUTORS,
    MAX_INLINE_SAMPLES,
    RuleDatasets,
    RuleOutcome,
    UnsupportedRuleTypeError,
    build_finding,
    execute,
)

__all__ = [
    "EXECUTORS",
    "ExecutionContext",
    "MAX_INLINE_SAMPLES",
    "RuleDatasets",
    "RuleOutcome",
    "UnsupportedRuleTypeError",
    "build_finding",
    "execute",
]
