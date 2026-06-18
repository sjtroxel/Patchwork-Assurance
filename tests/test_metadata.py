from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from patchwork_assurance.core.corpus.metadata import LawMetadata

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_fixture_loads():
    data = yaml.safe_load((FIXTURES / "fake-law.meta.yaml").read_text())
    meta = LawMetadata(**data)
    assert meta.law_id == "fake-law"
    assert meta.private_right_of_action is False
    assert "employment" in meta.scope_domains


def test_malformed_yaml_raises():
    bad = {"law_id": "bad", "jurisdiction": "Nowhere"}  # missing required fields
    with pytest.raises(ValidationError):
        LawMetadata(**bad)


def test_invalid_status_raises():
    data = yaml.safe_load((FIXTURES / "fake-law.meta.yaml").read_text())
    data["status"] = "not-a-real-status"
    with pytest.raises(ValidationError):
        LawMetadata(**data)
