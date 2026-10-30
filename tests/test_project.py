
import pytest

from services.compensation import (
    compa_ratio,
    band_position,
    normalize_salary
)


def test_compa_ratio():
    assert compa_ratio(900000, 1000000) == 0.9


def test_band_position():
    result = band_position(
        1000000, 800000, 1200000
    )
    assert result == 50.0


def test_below_band_position():
    result = band_position(
        700000, 800000, 1200000
    )
    assert result == -25.0


def test_invalid_midpoint():
    with pytest.raises(ValueError):
        compa_ratio(900000, 0)


def test_invalid_band_range():
    with pytest.raises(ValueError):
        band_position(900000, 1000000, 1000000)


def test_invalid_fte():
    with pytest.raises(ValueError):
        normalize_salary(
            600000, 0, "INR", None
        )
