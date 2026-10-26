"""The summary card must show both semi-amplitudes for an eccentric orbit."""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pytest

import phase_summary as ps


class TestFormatKp:

    def test_single_value_for_a_circular_orbit(self):
        assert ps.format_kp_cell(129.153, 0.0) == "129.153"

    def test_single_value_when_eccentricity_is_missing(self):
        assert ps.format_kp_cell(129.153, None) == "129.153"
        assert ps.format_kp_cell(129.153, np.nan) == "129.153"

    def test_single_value_below_the_eccentricity_threshold(self):
        assert ps.format_kp_cell(129.153, 0.005) == "129.153"

    def test_shows_both_values_for_an_eccentric_orbit(self):
        cell = ps.format_kp_cell(117.0, 0.218)

        assert "117.00" in cell
        assert "119.88" in cell  # 117 / sqrt(1 - 0.218**2)

    def test_placeholder_when_kp_is_unavailable(self):
        assert ps.format_kp_cell(None, 0.218) == "/"


class TestProjectedSemiAmplitude:
    """The line-of-sight amplitude of the planet is K_p sin i, with the true
    planetary mass in the denominator.  LTT 9779 b-like inputs, hand-computed:
    (2 pi G/P)^(1/3) M* sin(76.39 deg) / (M* + M_p)^(2/3) = 225.138 km/s."""

    ROW = {"pl_orbper": 0.7920641, "st_mass": 1.02, "pl_bmasse": 29.32,
           "pl_orbincl": 76.39}

    def test_includes_the_inclination(self):
        assert ps.compute_kp(self.ROW) == pytest.approx(225.138, abs=0.01)

    def test_edge_on_when_the_inclination_is_missing(self):
        row = {**self.ROW, "pl_orbincl": np.nan}
        # sin i = 1: 225.138 / sin(76.39 deg) = 231.64 km/s
        assert ps.compute_kp(row) == pytest.approx(231.64, abs=0.02)


class TestLimitFormatting:

    def test_upper_limit(self):
        assert ps.fmt_limit(0.058, 1, ".4f") == "< 0.0580"

    def test_lower_limit(self):
        assert ps.fmt_limit(123.44, -1, ".1f") == "> 123.4"

    def test_measured_value(self):
        assert ps.fmt_limit(30.5, 0, ".2f") == "30.50"
        assert ps.fmt_limit(30.5, np.nan, ".2f") == "30.50"

    def test_missing_value(self):
        assert ps.fmt_limit(np.nan, 1, ".2f") == "/"
