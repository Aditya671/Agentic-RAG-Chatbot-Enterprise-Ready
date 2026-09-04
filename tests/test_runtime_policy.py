from __future__ import annotations

import pytest

from backend.orchestration.runtime_policy import validate_top_k


def test_validate_top_k_accepts_positive_integer():
    assert validate_top_k(5) == 5


@pytest.mark.parametrize("value", [True, False, 1.0, "5", None])
def test_validate_top_k_rejects_non_integer_values(value):
    with pytest.raises(ValueError, match="integer"):
        validate_top_k(value)


@pytest.mark.parametrize("value", [0, -1])
def test_validate_top_k_rejects_non_positive_values(value):
    with pytest.raises(ValueError, match="similarity_top_k must be >= 1"):
        validate_top_k(value)
