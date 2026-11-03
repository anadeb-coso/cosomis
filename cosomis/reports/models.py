"""ReportTemplate lives in financial/models/report_template.py: the `reports` app label is owned by CDD
(its migrations are disabled here), so the table is migrated with the financial app."""
from financial.models.report_template import ReportTemplate  # noqa: F401
