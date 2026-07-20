"""Tests for the Keplerian planetary radial-velocity solver."""

import numpy as np
import pytest

import phase_kepler as pk


T0 = 2458046.6566
PERIOD = 4.971293


class TestCircularLimit:
    """For e = 0 the solver must reproduce the circular trace exactly."""

    @pytest.mark.parametrize("omega_p_deg", [0.0, 37.0, 90.0, 180.0, 291.5])
    def test_matches_kp_sin_two_pi_phase_for_any_omega(self, omega_p_deg):
        kp = 129.15
        t = T0 + np.linspace(-0.5 * PERIOD, 0.5 * PERIOD, 401)

        got = pk.planet_rv_kms(t, T0, PERIOD, 0.0, omega_p_deg, kp)

        phase = (t - T0) / PERIOD
        expected = kp * np.sin(2.0 * np.pi * phase)
        # 1e-6 km/s = 1 mm/s.  Absolute BJDs (~2.46e6) leave only ~1e-10 d of
        # float64 resolution, which maps to ~2e-8 km/s here, so anything
        # tighter would be testing the machine, not the model.
        assert np.allclose(got, expected, atol=1e-6)


class TestKeplerSolver:

    @pytest.mark.parametrize("ecc", [0.0, 0.1, 0.5, 0.9, 0.95])
    def test_solution_satisfies_keplers_equation(self, ecc):
        M = np.linspace(0.0, 2.0 * np.pi, 1001)

        E = pk.solve_kepler_E(M, ecc)

        assert np.allclose(E - ecc * np.sin(E), np.mod(M, 2.0 * np.pi),
                           atol=1e-10)

    def test_rejects_unbound_eccentricity(self):
        with pytest.raises(ValueError):
            pk.solve_kepler_E(np.array([0.3]), 1.0)


class TestEphemerisAnchoring:
    """t = T0 must be mid-transit, i.e. nu(T0) = pi/2 - omega_star."""

    @pytest.mark.parametrize("ecc", [0.0, 0.12, 0.42, 0.85])
    @pytest.mark.parametrize("omega_p_deg", [0.0, 63.0, 214.0])
    def test_true_anomaly_at_t0_is_transit_anomaly(self, ecc, omega_p_deg):
        nu = pk.true_anomaly(np.array([T0]), T0, PERIOD, ecc, omega_p_deg)[0]

        nu_tr = 0.5 * np.pi - np.radians(omega_p_deg + 180.0)
        # compare as angles, so that 2*pi wraps do not count as differences
        assert np.isclose(np.cos(nu), np.cos(nu_tr), atol=1e-9)
        assert np.isclose(np.sin(nu), np.sin(nu_tr), atol=1e-9)


class TestKpEccentric:

    def test_divides_by_sqrt_one_minus_e_squared(self):
        assert pk.kp_eccentric(129.15, 0.6) == pytest.approx(129.15 / 0.8)

    def test_returns_kp_unchanged_for_circular_orbit(self):
        assert pk.kp_eccentric(129.15, 0.0) == pytest.approx(129.15)

    def test_returns_none_for_missing_kp(self):
        assert pk.kp_eccentric(None, 0.3) is None


class TestOmegaEnvelope:
    """With omega unknown, the envelope must bracket every possible omega."""

    def test_brackets_the_trace_of_an_arbitrary_omega(self):
        ecc, kp = 0.35, 118.0
        t = T0 + np.linspace(-0.1, 0.1, 51)

        lo, hi, _ = pk.omega_envelope(t, T0, PERIOD, ecc, kp)

        for omega_p_deg in (0.0, 17.0, 123.0, 250.0, 359.0):
            trace = pk.planet_rv_kms(t, T0, PERIOD, ecc, omega_p_deg, kp)
            assert np.all(trace >= lo - 1e-9)
            assert np.all(trace <= hi + 1e-9)

    def test_envelope_is_degenerate_for_circular_orbit(self):
        t = T0 + np.linspace(-0.1, 0.1, 51)

        lo, hi, _ = pk.omega_envelope(t, T0, PERIOD, 0.0, 118.0)

        assert np.allclose(lo, hi, atol=1e-6)


# Literature parameters for the three eccentric systems raised in review.
# Values are rounded; K_p is the circular orbital speed 2*pi*a/P, which is what
# the pipeline's compute_kp produces.
#   GJ 3470 b   Kosiarek+2019, Awiphan+2016   P=3.3366 d, e=0.114, w=98 deg
#   GJ 436 b    Trifonov+2018, Lanotte+2014   P=2.6439 d, e=0.152, w=327 deg
#   HAT-P-11 b  Yee+2018                      P=4.8878 d, e=0.218, w=18 deg
KNOWN_ECCENTRIC = [
    ("GJ 3470 b",  3.3366, 0.114,  98.0, 122.0),
    ("GJ 436 b",   2.6439, 0.152, 327.0, 118.0),
    ("HAT-P-11 b", 4.8878, 0.218,  18.0, 117.0),
]


class TestKnownEccentricSystems:
    """
    The cases the reviewer cited: the circular approximation must be shown to
    be wrong by of order ten km/s, i.e. the solver reproduces the very problem
    it was added to fix.
    """

    @pytest.mark.parametrize(
        "name,period,ecc,omega_p_deg,kp", KNOWN_ECCENTRIC,
        ids=[c[0] for c in KNOWN_ECCENTRIC],
    )
    def test_deviates_from_circular_by_at_least_5_kms(
        self, name, period, ecc, omega_p_deg, kp,
    ):
        t0 = 2458000.0
        # one full orbit, the window over which an observer might plan
        t = t0 + np.linspace(-0.5 * period, 0.5 * period, 2001)
        kp_ecc = pk.kp_eccentric(kp, ecc)

        keplerian = pk.planet_rv_kms(t, t0, period, ecc, omega_p_deg, kp_ecc)
        circular = kp * np.sin(2.0 * np.pi * (t - t0) / period)

        max_dev = float(np.max(np.abs(keplerian - circular)))
        assert max_dev > 5.0, f"{name}: max deviation only {max_dev:.2f} km/s"

    @pytest.mark.parametrize(
        "name,period,ecc,omega_p_deg,kp", KNOWN_ECCENTRIC,
        ids=[c[0] for c in KNOWN_ECCENTRIC],
    )
    def test_deviation_is_already_significant_during_transit(
        self, name, period, ecc, omega_p_deg, kp,
    ):
        """A few km/s inside +-3 h of mid-transit is what breaks a CCF plan."""
        t0 = 2458000.0
        t = t0 + np.linspace(-3.0 / 24.0, 3.0 / 24.0, 361)
        kp_ecc = pk.kp_eccentric(kp, ecc)

        keplerian = pk.planet_rv_kms(t, t0, period, ecc, omega_p_deg, kp_ecc)
        circular = kp * np.sin(2.0 * np.pi * (t - t0) / period)

        max_dev = float(np.max(np.abs(keplerian - circular)))
        assert max_dev > 1.0, f"{name}: max deviation only {max_dev:.2f} km/s"
