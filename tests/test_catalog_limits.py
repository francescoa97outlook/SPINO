"""
Limit flags of the NASA Exoplanet Archive (pl_*lim: 1 = upper limit,
-1 = lower limit) must reach the composite row, and e and omega, which are
fitted together, must come from the same reference.

LTT 9779 b is the case in point: Edwards et al. (2023) give e < 0.058, while
the only argument of periastron on record, 90 deg, belongs to the circular
fit of Jenkins et al. (2020).
"""

import numpy as np
import pandas as pd
import pytest

import nea_fetch
import phase_scheduler as sched


def rows(*specs):
    """One DataFrame row per spec dict, with the ephemeris columns filled."""
    out = []
    for spec in specs:
        base = dict(pl_name="TEST b", pl_orbper=0.7920641,
                    pl_tranmid=2459043.3106, ra=356.0, dec=-37.6,
                    pl_orbeccen=np.nan, pl_orbeccenlim=np.nan,
                    pl_orblper=np.nan, pl_orblperlim=np.nan,
                    pl_bmasse=np.nan, pl_bmasselim=np.nan)
        base.update(spec)
        out.append(base)
    return pd.DataFrame(out)


LTT9779B_LIKE = rows(
    dict(pl_refname="Edwards et al. 2023", pl_pubdate="2023-10",
         pl_orbeccen=0.058, pl_orbeccenlim=1),
    dict(pl_refname="Jenkins et al. 2020", pl_pubdate="2020-09",
         pl_orbeccen=0.0, pl_orbeccenlim=0, pl_orblper=90.0, pl_orblperlim=0),
)

# Composite geometry of LTT 9779 b in the 2026-07-17 snapshot.
GEOMETRY = dict(pl_name="LTT 9779 b", pl_orbper=0.7920641, pl_orbsmax=0.01679,
                st_rad=0.949, pl_rade=4.72, st_mass=1.02, pl_orbincl=76.39,
                pl_trandur=np.nan)


@pytest.fixture(autouse=True)
def _reset_warnings():
    sched._geom_omega_warned.clear()
    yield


class TestComposition:

    def test_upper_limit_reaches_the_composite_with_its_flag(self):
        comp = sched.compose_best_rows(LTT9779B_LIKE).iloc[0]

        assert comp["pl_orbeccen"] == pytest.approx(0.058)
        assert comp["pl_orbeccenlim"] == 1

    def test_omega_comes_from_the_same_reference_as_e(self):
        comp = sched.compose_best_rows(LTT9779B_LIKE).iloc[0]

        assert np.isnan(comp["pl_orblper"])

    def test_omega_is_kept_when_that_reference_reports_it(self):
        df = rows(
            dict(pl_refname="A 2024", pl_pubdate="2024-01",
                 pl_orbeccen=0.2, pl_orbeccenlim=0, pl_orblper=40.0,
                 pl_orblperlim=0),
            dict(pl_refname="B 2019", pl_pubdate="2019-01",
                 pl_orbeccen=0.1, pl_orbeccenlim=0, pl_orblper=50.0,
                 pl_orblperlim=0),
        )

        comp = sched.compose_best_rows(df).iloc[0]

        assert comp["pl_orbeccen"] == pytest.approx(0.2)
        assert comp["pl_orblper"] == pytest.approx(40.0)
        assert comp["_field_sources"]["pl_orblper"] == "A 2024"

    def test_lower_limits_are_not_used_as_eccentricities(self):
        df = rows(dict(pl_refname="T 2015", pl_pubdate="2015-01",
                       pl_orbeccen=0.04, pl_orbeccenlim=-1))

        comp = sched.compose_best_rows(df).iloc[0]

        assert np.isnan(comp["pl_orbeccen"])

    def test_a_measured_mass_is_preferred_to_a_more_recent_limit(self):
        df = rows(
            dict(pl_refname="New 2024", pl_pubdate="2024-01",
                 pl_bmasse=50.0, pl_bmasselim=1),
            dict(pl_refname="Old 2018", pl_pubdate="2018-01",
                 pl_bmasse=30.0, pl_bmasselim=0),
        )

        comp = sched.compose_best_rows(df).iloc[0]

        assert comp["pl_bmasse"] == pytest.approx(30.0)
        assert comp["pl_bmasselim"] == 0

    def test_a_mass_limit_is_used_when_nothing_better_exists(self):
        df = rows(dict(pl_refname="Only 2024", pl_pubdate="2024-01",
                       pl_bmasse=50.0, pl_bmasselim=1))

        comp = sched.compose_best_rows(df).iloc[0]

        assert comp["pl_bmasse"] == pytest.approx(50.0)
        assert comp["pl_bmasselim"] == 1

    def test_catalogues_without_limit_columns_still_compose(self):
        df = rows(dict(pl_refname="A 2024", pl_pubdate="2024-01",
                       pl_orbeccen=0.2, pl_orblper=40.0)).drop(
            columns=["pl_orbeccenlim", "pl_orblperlim", "pl_bmasselim"])

        comp = sched.compose_best_rows(df).iloc[0]

        assert comp["pl_orbeccen"] == pytest.approx(0.2)
        assert comp["pl_orblper"] == pytest.approx(40.0)

    def test_the_fetcher_downloads_every_limit_flag_the_composer_reads(self):
        assert {"pl_orbeccenlim", "pl_orblperlim", "pl_bmasselim"} <= set(
            nea_fetch.NEA_COLUMNS)


class TestGeometryOfAnUpperLimit:

    def row(self):
        return pd.Series({**GEOMETRY, "pl_orbeccen": 0.058,
                          "pl_orbeccenlim": 1, "pl_orblper": np.nan})

    def test_is_circular_by_default(self):
        # a/R* = 0.01679/(0.949*0.00465047) = 3.8044; b = a/R* cos(76.39 deg)
        # = 0.8952 for transit and occultation alike.  phi_sec carries only
        # the Roemer delay 2a/c = 16.76 s, i.e. 0.5 + 0.000245.
        geom = sched.compute_transit_geometry(self.row())

        assert geom["b"] == pytest.approx(0.8952, abs=1e-3)
        assert geom["b_occ"] == pytest.approx(geom["b"])
        assert geom["phi_sec"] == pytest.approx(0.500245, abs=2e-6)
        assert (geom["quad_pre_ph"], geom["quad_post_ph"]) == (0.25, 0.75)
        assert "ecc_upper_limit" in geom["geom_flags"]

    def test_is_used_as_the_eccentricity_when_the_option_is_set(self):
        # e = 0.058 shifts the eclipse by up to 42 min on this orbit and no
        # omega comes with it, so the eclipse windows are suppressed.
        geom = sched.compute_transit_geometry(
            self.row(), ecc_upper_limits_as_values=True)

        assert geom["ecc"] == pytest.approx(0.058)
        assert np.isnan(geom["phi_sec"])
        assert "ecc_upper_limit" in geom["geom_flags"]


class TestRadialVelocityOfAnUpperLimit:

    def row(self):
        return pd.Series({**GEOMETRY, "pl_orbeccen": 0.12,
                          "pl_orbeccenlim": 1, "pl_orblper": np.nan})

    def test_is_circular_by_default(self):
        ecc, omega_p_deg = sched.rv_orbit_shape(self.row())

        assert ecc is None and omega_p_deg is None

    def test_spans_every_omega_at_the_limit_when_the_option_is_set(self):
        ecc, omega_p_deg = sched.rv_orbit_shape(
            self.row(), ecc_upper_limits_as_values=True)

        assert ecc == pytest.approx(0.12)
        assert omega_p_deg is None


class TestCustomOverrides:

    def test_a_custom_eccentricity_is_a_value_not_a_limit(self):
        base = {**GEOMETRY, "pl_orbeccen": 0.058, "pl_orbeccenlim": 1}

        merged = sched.merge_custom_planet(base, {"pl_orbeccen": 0.1})

        assert merged["pl_orbeccen"] == pytest.approx(0.1)
        assert merged["pl_orbeccenlim"] == 0

    def test_a_custom_mass_is_a_value_not_a_limit(self):
        base = {**GEOMETRY, "pl_bmasse": 50.0, "pl_bmasselim": 1}

        merged = sched.merge_custom_planet(base, {"pl_bmasse": 30.0})

        assert merged["pl_bmasselim"] == 0
