"""Failed or truncated simulator output must remain reportable, never successful."""

import pytest

from tools.rtems_periodic_probe_report import check_raw_status
from test_periodic_public import public_evidence


def test_truncated_failed_output_remains_reportable():
    plan, _ = public_evidence()
    row = dict(execution_status='failed', returncode=124, mode=0, trace=False, empty=False)
    check_raw_status(row, plan, 'PERIODIC {"kind":"job","task":')


def test_truncated_output_cannot_be_reported_as_success():
    plan, _ = public_evidence()
    row = dict(execution_status='ok', returncode=0, mode=0, trace=False, empty=False)
    with pytest.raises(ValueError, match='successful'):
        check_raw_status(row, plan, 'PERIODIC {"kind":"job","task":')
