from __future__ import annotations

import pytest

from backend.orchestration.runtime_policy import validate_top_k


def test_validate_top_k_accepts_positive_integer():
    assert validate_top_k(5) == 5


@pytest.mark.parametrize("value", [True, False, 1.0, "5", None])
def test_validate_top_k_rejects_non_integer_values(value):
    with pytest.raises(ValueError, match="integer"):
        validate_top_k(value)


def test_validate_top_k_rejects_non_positive_values():
    with pytest.raises(ValueError, match=">= 1"):
        validate_top_k(0)
    with pytest.raises(ValueError, match=">= 1"):
        validate_top_k(-1)
