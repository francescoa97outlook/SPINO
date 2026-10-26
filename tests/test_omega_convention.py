"""
The archive stores the argument of periastron as published, which for radial-
velocity solutions is that of the star's reflex orbit, omega_star: the transit
falls at true anomaly pi/2 - omega_star (Winn 2010, Eq. 6; the NEA Transit
Service makes the same assumption).  Reading pl_orblper as the planet's omega
puts every eccentric eclipse on the wrong side of mid-orbit and swaps the
transit and occultation impact parameters.

The expected values below are measurements, not outputs of this code.
"""

import numpy as np
import pandas as pd
import pytest

import phase_kepler as pk
import phase_scheduler as sched


def catalogue_row(**fields):
    base = dict(pl_name="TEST b", pl_trandur=np.nan, pl_orbeccenlim=0)
    base.update(fields)
    return pd.Series(base)


# Composite elements of the 2026-07-17 snapshot; e and omega of XO-3 b are
# those of Wong et al. (2014), the paper that measured its eclipse phase.
XO3B = dict(pl_name="XO-3 b", pl_orbper=3.19152255771, pl_orbeccen=0.2769,
            pl_orblper=347.2, pl_orbsmax=0.04815, st_rad=1.523,
            pl_rade=14.79585452, st_mass=1.449, pl_orbincl=83.66)
GJ436B = dict(pl_name="GJ 436 b", pl_orbper=2.64389803, pl_orbeccen=0.1634,
              pl_orblper=327.31, pl_orbsmax=0.02849, st_rad=0.464,
              pl_rade=3.85, st_mass=0.452, pl_orbincl=86.87)
HD80606B = dict(pl_name="HD 80606 b", pl_orbper=111.4367, pl_orbeccen=0.93183,
                pl_orblper=-58.887, pl_orbsmax=0.4603, st_rad=1.05,
                pl_rade=11.56766808, st_mass=1.05, pl_orbincl=89.24)


@pytest.fixture(autouse=True)
def _reset_warnings():
    sched._geom_omega_warned.clear()
    yield


class TestEclipsePhaseMatchesSpitzer:

    def test_xo3b(self):
        # Wong et al. (2014): phase 0.67004 +/- 0.00013.  A tolerance of
        # 0.001 in phase is 4.6 min on this orbit.
        geom = sched.compute_transit_geometry(catalogue_row(**XO3B))

        assert geom["phi_sec"] == pytest.approx(0.67004, abs=1e-3)

    def test_gj436b(self):
        # Knutson et al. (2011): phase 0.58672 +/- 0.00017.  The composite
        # elements come from a different solution, hence 0.0015 (5.7 min).
        geom = sched.compute_transit_geometry(catalogue_row(**GJ436B))

        assert geom["phi_sec"] == pytest.approx(0.58672, abs=1.5e-3)


class TestTransitDurationMatchesCatalogue:

    def test_hd80606b(self):
        # Catalogued T14 = 11.98 h.  With omega read as the planet's the
        # transit lands near periastron and lasts about 2 h.
        geom = sched.compute_transit_geometry(catalogue_row(**HD80606B))

        assert geom["t14_h"] == pytest.approx(11.98, abs=0.5)

    def test_transit_and_occultation_impact_parameters_are_not_swapped(self):
        # e*sin(omega_star) = 0.2769*sin(347.2 deg) = -0.0613 < 0, so the
        # planet is further from the star at transit than at occultation and
        # crosses the disc further from its centre: b_tra > b_occ.
        geom = sched.compute_transit_geometry(catalogue_row(**XO3B))

        assert geom["b"] > geom["b_occ"]


class TestPlanetRadialVelocityAtMidTransit:

    def test_has_the_sign_of_minus_e_cos_omega_star(self):
        # At conjunction the star recedes at K_star*e*cos(omega_star), so the
        # planet approaches: V_p(T0) = -K_p,ecc * e * cos(omega_star).
        # K_p = 100 km/s -> K_p,ecc = 100/sqrt(1 - 0.2769^2) = 104.069 km/s,
        # e*cos(347.2 deg) = 0.27002  ->  V_p(T0) = -28.10 km/s.
        ecc, omega_p_deg = sched.rv_orbit_shape(catalogue_row(**XO3B))

        sol = pk.orbit_solution(np.array([2458000.0]), 2458000.0,
                                XO3B["pl_orbper"], ecc, omega_p_deg, 100.0)

        assert sol["mode"] == "keplerian"
        assert sol["v_adopted"][0] == pytest.approx(-28.10, abs=0.05)

    def test_unknown_omega_gives_the_envelope(self):
        ecc, omega_p_deg = sched.rv_orbit_shape(
            catalogue_row(**{**XO3B, "pl_orblper": np.nan}))

        assert ecc == pytest.approx(0.2769)
        assert omega_p_deg is None

    def test_missing_eccentricity_gives_a_circular_orbit(self):
        ecc, omega_p_deg = sched.rv_orbit_shape(
            catalogue_row(**{**XO3B, "pl_orbeccen": np.nan}))

        assert ecc is None
