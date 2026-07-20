"""The summary card must show both semi-amplitudes for an eccentric orbit."""

import matplotlib
matplotlib.use("Agg")

import numpy as np

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
