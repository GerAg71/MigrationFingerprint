"""Report rendering (MS-2.3): findings.html + the five client-facing
reconciliation reports (spec §13.1–13.3), Jinja2 templates in templates/."""

from src.report.aggregates import compute_reconciliation, quality_sections
from src.report.html import (
    RECON_KINDS,
    render_findings_html,
    render_reconciliation_html,
)

# NB: src.report.signoff is imported directly by its callers, never from this
# package init — it depends on src.learning, which depends on src.runner,
# which imports this package (a re-export here closes the import cycle).

__all__ = [
    "RECON_KINDS",
    "compute_reconciliation",
    "quality_sections",
    "render_findings_html",
    "render_reconciliation_html",
]
