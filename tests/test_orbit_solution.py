"""
Tests for the branch logic that picks circular / Keplerian / omega-envelope.

This is the decision the reviewer's second comment is about, so it is kept
free of astropy and of the event machinery and tested on its own.
"""

import numpy as np
import pytest

import phase_kepler as pk


T0 = 2458000.0
PERIOD = 4.8878
KP = 117.0


def _grid():
    return T0 + np.linspace(-0.1, 0.1, 101)


class TestModeSelection:

    def test_circular_when_eccentricity_missing(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, None, 18.0, KP)

        assert sol["mode"] == "circular"
        assert sol["omega_used"] is None
        assert sol["v_lo"] is None and sol["v_hi"] is None

    def test_circular_when_eccentricity_below_threshold(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.5 * pk.ECC_MIN, 18.0, KP)

        assert sol["mode"] == "circular"

    def test_keplerian_when_eccentricity_and_omega_known(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, 18.0, KP)

        assert sol["mode"] == "keplerian"
        assert sol["omega_used"] == pytest.approx(18.0)
        assert sol["v_lo"] is None and sol["v_hi"] is None

    def test_envelope_when_omega_missing(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, None, KP)

        assert sol["mode"] == "envelope"
        assert sol["omega_used"] is None
        assert sol["v_lo"] is not None and sol["v_hi"] is not None

    def test_envelope_when_omega_is_nan(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, np.nan, KP)

        assert sol["mode"] == "envelope"


class TestAdoptedTrace:

    def test_circular_mode_reproduces_the_legacy_formula(self):
        t = _grid()

        sol = pk.orbit_solution(t, T0, PERIOD, 0.0, 18.0, KP)

        expected = KP * np.sin(2.0 * np.pi * (t - T0) / PERIOD)
        assert np.allclose(sol["v_adopted"], expected, atol=1e-6)

    def test_circular_reference_is_always_the_legacy_formula(self):
        t = _grid()

        sol = pk.orbit_solution(t, T0, PERIOD, 0.218, 18.0, KP)

        expected = KP * np.sin(2.0 * np.pi * (t - T0) / PERIOD)
        assert np.allclose(sol["v_circ"], expected, atol=1e-6)

    def test_keplerian_adopted_trace_uses_the_corrected_amplitude(self):
        t = _grid()

        sol = pk.orbit_solution(t, T0, PERIOD, 0.218, 18.0, KP)

        expected = pk.planet_rv_kms(
            t, T0, PERIOD, 0.218, 18.0, pk.kp_eccentric(KP, 0.218),
        )
        assert np.allclose(sol["v_adopted"], expected, atol=1e-9)

    def test_envelope_adopted_trace_is_the_circular_one(self):
        """With omega unknown there is no preferred trace, so the plot keeps
        the circular curve as the drawn line and shows the envelope around it."""
        t = _grid()

        sol = pk.orbit_solution(t, T0, PERIOD, 0.218, None, KP)

        assert np.allclose(sol["v_adopted"], sol["v_circ"], atol=1e-9)


class TestMaxDeviation:

    def test_zero_for_circular_orbit(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.0, 18.0, KP)

        assert sol["max_dev_circ"] == pytest.approx(0.0, abs=1e-6)

    def test_matches_the_keplerian_minus_circular_difference(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, 18.0, KP)

        expected = np.max(np.abs(sol["v_adopted"] - sol["v_circ"]))
        assert sol["max_dev_circ"] == pytest.approx(expected)

    def test_envelope_reports_the_worst_case_over_all_omega(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, None, KP)

        worst = max(
            np.max(np.abs(sol["v_lo"] - sol["v_circ"])),
            np.max(np.abs(sol["v_hi"] - sol["v_circ"])),
        )
        assert sol["max_dev_circ"] == pytest.approx(worst)


class TestKpReporting:

    def test_reports_both_semi_amplitudes(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, 18.0, KP)

        assert sol["kp_circ"] == pytest.approx(KP)
        assert sol["kp_ecc"] == pytest.approx(KP / np.sqrt(1 - 0.218 ** 2))

    def test_kp_ecc_equals_kp_circ_for_circular_orbit(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.0, 18.0, KP)

        assert sol["kp_ecc"] == pytest.approx(sol["kp_circ"])


class TestEccentricityOutOfRange:
    """
    A dirty catalogue value must not stop a scheduling run: e outside [0,1)
    falls back to circular with an explicit warning, instead of letting the
    Kepler solver's ValueError propagate.
    """

    @pytest.mark.parametrize("ecc", [1.0, 1.4, -0.2])
    def test_falls_back_to_circular_instead_of_raising(self, ecc):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, ecc, 18.0, KP)

        assert sol is not None
        assert sol["mode"] == "circular"

    @pytest.mark.parametrize("ecc", [1.0, 1.4, -0.2])
    def test_says_the_value_was_rejected(self, ecc):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, ecc, 18.0, KP)

        msg = pk.describe_orbit_solution(sol).lower()
        assert "out of range" in msg or "rejected" in msg
        assert str(ecc) in msg

    def test_emits_no_numpy_warning(self, recwarn):
        pk.orbit_solution(_grid(), T0, PERIOD, 1.4, 18.0, KP)

        assert not [w for w in recwarn if issubclass(w.category, RuntimeWarning)]

    def test_trace_is_the_plain_circular_one(self):
        t = _grid()

        sol = pk.orbit_solution(t, T0, PERIOD, 1.4, 18.0, KP)

        expected = KP * np.sin(2.0 * np.pi * (t - T0) / PERIOD)
        assert np.allclose(sol["v_adopted"], expected, atol=1e-6)


class TestUnusableInputs:

    def test_returns_none_without_kp(self):
        assert pk.orbit_solution(_grid(), T0, PERIOD, 0.2, 18.0, None) is None

    def test_returns_none_for_non_finite_kp(self):
        assert pk.orbit_solution(
            _grid(), T0, PERIOD, 0.2, 18.0, float("nan"),
        ) is None


class TestLogMessage:
    """The spec requires the run log to state which branch was taken."""

    def test_names_the_omega_actually_used(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, 18.0, KP)

        msg = pk.describe_orbit_solution(sol)
        assert "18.0" in msg and "0.218" in msg
        assert "keplerian" in msg.lower()

    def test_announces_the_envelope_and_its_width(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.218, None, KP)

        msg = pk.describe_orbit_solution(sol)
        assert "envelope" in msg.lower()
        assert "0.218" in msg

    def test_says_nothing_alarming_for_a_circular_orbit(self):
        sol = pk.orbit_solution(_grid(), T0, PERIOD, 0.0, 18.0, KP)

        msg = pk.describe_orbit_solution(sol)
        assert "circular" in msg.lower()
