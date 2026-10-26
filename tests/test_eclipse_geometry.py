"""
Exact Keplerian secondary-eclipse geometry.

Before this fix, `compute_event_windows` hardcoded the outer pre-/post-
eclipse bounds at phase 0.25 / 0.75 (exact only for a circular orbit) while
letting only the inner bound move with eccentricity, and `phi_sec` itself
used Winn (2010) Eq. 33, a first-order approximation in e.  For e = 0.3,
omega_p = 0 the true quadratures sit at 0.156 / 0.656, well inside 0.25 /
0.75, so the old fixed outer bound produced an empty pre-eclipse window for
some systems -- exactly the bug this test suite regresses against.
"""

import numpy as np
import pandas as pd
import pytest

import phase_kepler as pk
import phase_scheduler as sched


def row(**overrides):
    base = dict(
        pl_name="TEST b", pl_orbper=4.8878, pl_orbeccen=0.0, pl_orblper=np.nan,
        pl_orbsmax=0.0530, st_rad=0.75, pl_rade=4.36, st_mass=0.81,
        pl_orbincl=89.0, pl_trandur=np.nan,
    )
    base.update(overrides)
    return pd.Series(base)


@pytest.fixture(autouse=True)
def _reset_warnings():
    sched._geom_omega_warned.clear()
    yield


class TestReferenceValues:
    """Verified against an independent brute-force Kepler solve (see the
    implementation plan); the exact helpers must reproduce these to 1e-4."""

    @pytest.mark.parametrize("ecc, omega_p, phi_exp, pre_exp, post_exp", [
        (0.0, 0.0,   0.5000, 0.2500, 0.7500),
        (0.0, 123.0, 0.5000, 0.2500, 0.7500),
        (0.1, 0.0,   0.4364, 0.2182, 0.7182),
        (0.3, 0.0,   0.3119, 0.1560, 0.6560),
        (0.5, 180.0, 0.8045, 0.4022, 0.9022),
        (0.5, 90.0,  0.5000, 0.4022, 0.5978),
    ])
    def test_reference_table(self, ecc, omega_p, phi_exp, pre_exp, post_exp):
        phi = pk.secondary_eclipse_phase(ecc, omega_p)
        pre, post = pk.quadrature_phases(ecc, omega_p)

        assert phi == pytest.approx(phi_exp, abs=1e-4)
        assert pre == pytest.approx(pre_exp, abs=1e-4)
        assert post == pytest.approx(post_exp, abs=1e-4)

    @pytest.mark.parametrize("omega_p", [0.0, 45.0, 90.0, 180.0, 270.0, 359.0])
    def test_circular_orbit_is_omega_independent(self, omega_p):
        assert pk.secondary_eclipse_phase(0.0, omega_p) == pytest.approx(0.5)
        assert pk.quadrature_phases(0.0, omega_p) == (
            pytest.approx(0.25), pytest.approx(0.75))


class TestOrderingInvariant:

    @pytest.mark.parametrize("ecc", np.linspace(0.0, 0.9, 10))
    @pytest.mark.parametrize("omega_p", np.linspace(0.0, 359.0, 8))
    def test_quad_pre_lt_phi_sec_lt_quad_post(self, ecc, omega_p):
        phi = pk.secondary_eclipse_phase(ecc, omega_p)
        pre, post = pk.quadrature_phases(ecc, omega_p)

        assert pre < phi < post


class TestRegressionForReportedBug:
    """e = 0.3, omega_p = 0: the previous fixed-0.25 outer bound produced an
    empty pre-eclipse window for this fixture (verified by hand against the
    old formula); the exact-quadrature bound must not."""

    def test_pre_eclipse_window_is_not_empty(self):
        # a_Rs = 3 (grazing-ish, wide T14_sec) is exactly what starves the
        # old fixed pre_start = 0.25 of room: phi_sec - half_ph_sec ~ 0.245.
        a_AU = 3.0 * 0.75 * 0.00465047
        # omega_p = 0 is omega_star = 180 in the catalogue's convention.
        geom = sched.compute_transit_geometry(
            row(pl_orbeccen=0.3, pl_orblper=180.0, pl_orbsmax=a_AU))

        windows = sched.compute_event_windows(geom)

        assert windows["pre_eclipse"] != []
        pre_start, pre_end = windows["pre_eclipse"][0]
        assert pre_start == pytest.approx(geom["quad_pre_ph"])
        assert pre_end > pre_start


class TestNonOccultingGeometry:
    """A system can transit and still not be occulted (or vice versa)
    whenever e*sin(omega_star) is sizeable: b_occ uses the opposite sign
    from the transit's b."""

    def test_b_occ_exceeds_one_plus_k_suppresses_both_eclipse_windows(self):
        incl = 87.0
        a_Rs = 0.7 / np.cos(np.radians(incl))
        a_AU = a_Rs * 0.75 * 0.00465047
        # pl_orblper is omega_star: 90 deg puts the transit at periastron
        # (e*sin(omega_star) = +0.6, small b) and the occultation at
        # apoastron, four times further out in projection.
        geom = sched.compute_transit_geometry(row(
            pl_orbper=4.0, pl_orbeccen=0.6, pl_orblper=90.0,
            pl_orbsmax=a_AU, pl_orbincl=incl,
        ))

        assert geom["b_occ"] > 1.0 + geom["k"]
        assert "nonocculting" in geom["geom_flags"]
        assert np.isnan(geom["t14_sec_h"])

        windows = sched.compute_event_windows(geom)

        assert windows["pre_eclipse"] == []
        assert windows["post_eclipse"] == []
        # The transit itself is unaffected: b (not b_occ) still transits.
        assert windows["transit"] != []


class TestEccentricWithUnknownOmegaSuppressesEclipse:

    def test_both_eclipse_windows_empty_transit_present(self):
        geom = sched.compute_transit_geometry(
            row(pl_orbeccen=0.218, pl_orblper=np.nan))

        assert np.isnan(geom["phi_sec"])
        assert np.isnan(geom["quad_pre_ph"])
        assert np.isnan(geom["quad_post_ph"])

        windows = sched.compute_event_windows(geom)

        assert windows["pre_eclipse"] == []
        assert windows["post_eclipse"] == []
        assert windows["transit"] != []


class TestLightTravelDelay:

    def test_circular_orbit_shift_matches_two_a_over_c(self):
        P = 3.0
        a_AU = 0.04
        geom = sched.compute_transit_geometry(
            row(pl_orbper=P, pl_orbeccen=0.0, pl_orblper=np.nan, pl_orbsmax=a_AU))

        dt_s = (geom["phi_sec"] - 0.5) * P * 86400.0
        expected_s = 2.0 * a_AU * 499.004784

        assert dt_s == pytest.approx(expected_s, abs=1.0)
