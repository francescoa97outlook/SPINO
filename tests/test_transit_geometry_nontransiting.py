"""
A composite geometry assembled from mismatched references (see
compose_best_rows / test_compose_orbsmax_kepler.py) can require b > 1+k --
Eq. 14 would then need sqrt() of a negative number.  That must not silently
become a NaN that passes every comparison downstream in match_events; it
must either fall back to the catalog's pl_trandur, or stay NaN with a
warning that reaches the run log.

Fixture values are the actual HD 219666 b composite row that exposed this:
P, i, Rp, Rs, M* each came from a different NEA reference, and
pl_orbsmax=0.104 AU (Oddo et al. 2023) combined with i=86.42 deg (Murphy et
al. 2025) gives b=1.315, which does not transit at all.
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

import phase_scheduler as sched


def composite_row(pl_trandur=np.nan, pl_orbsmax=0.104):
    return pd.Series({
        "pl_name": "HD 219666 b",
        "pl_orbper": 6.034468,
        "pl_orbsmax": pl_orbsmax,
        "pl_orbincl": 86.42,
        "pl_orbeccen": 0.05,
        "pl_orblper": 0.0,
        "pl_rade": 4.898,
        "st_rad": 1.059,
        "st_mass": 1.02,
        "pl_trandur": pl_trandur,
    })


@pytest.fixture(autouse=True)
def _reset_warnings():
    sched._geom_omega_warned.clear()
    yield


class TestNonTransitingCompositeGeometry:

    def test_b_exceeds_one_plus_k(self):
        # Sanity check on the fixture itself: b > 1+k is exactly the
        # condition this test suite is about.
        geom = sched.compute_transit_geometry(composite_row())

        assert geom["b"] > 1.0 + geom["k"]
        assert geom["b"] == pytest.approx(1.3153, abs=1e-3)
        assert geom["k"] == pytest.approx(0.04236, abs=1e-4)

    def test_t14_is_nan_without_catalog_trandur(self):
        geom = sched.compute_transit_geometry(composite_row())

        assert np.isnan(geom["t14_h"])
        assert np.isnan(geom["t23_h"])
        assert np.isnan(geom["half_ph"])
        assert np.isnan(geom["t14_sec_h"])
        assert np.isnan(geom["half_ph_sec"])
        assert geom["grazing"] is True
        # phi_sec (Eq. 33) does not depend on whether the object transits,
        # so it must still be a real number, not swept into NaN with T14.
        assert np.isfinite(geom["phi_sec"])

    def test_warns_when_geometry_does_not_transit(self, capsys):
        sched.compute_transit_geometry(composite_row())

        out = capsys.readouterr().out.lower()
        assert "hd 219666 b" in out
        assert "does not transit" in out

    def test_warns_only_once_per_target(self):
        for _ in range(3):
            sched.compute_transit_geometry(composite_row())

        hits = [k for k in sched._geom_omega_warned
                if k == ("HD 219666 b", "nontransiting_nan")]
        assert len(hits) == 1

    def test_uses_catalog_trandur_when_available(self, capsys):
        geom = sched.compute_transit_geometry(composite_row(pl_trandur=2.028))

        assert geom["t14_h"] == pytest.approx(2.028)
        assert geom["t23_h"] == 0.0
        assert geom["t14_sec_h"] == pytest.approx(2.028)
        assert geom["grazing"] is True
        assert np.isfinite(geom["half_ph"])

        out = capsys.readouterr().out.lower()
        assert "pl_trandur" in out


class TestConsistentGeometryIsUnaffected:

    def test_correct_orbsmax_gives_finite_transiting_geometry(self):
        # Regression guard: with the *correct* semi-major axis (Esposito et
        # al. 2019, Kepler-consistent for this P and M*), the same row must
        # still produce a normal, finite T14 -- this patch must not affect
        # the sane path.
        geom = sched.compute_transit_geometry(composite_row(pl_orbsmax=0.06356))

        assert np.isfinite(geom["t14_h"])
        assert geom["t14_h"] == pytest.approx(2.373, abs=0.01)
        assert geom["b"] == pytest.approx(0.8039, abs=0.01)
        assert geom["grazing"] is False


class TestSilentTwoHourFallbackNowLogs:
    """
    The pre-existing fallback (missing semi-major axis / stellar radius, at
    the top of compute_transit_geometry) is unchanged in behavior -- it
    still uses pl_trandur when available, else a 2.0 h placeholder -- but
    both paths must now log, instead of letting an invented duration pass
    silently for a measured one.
    """

    def _no_geometry_row(self, **overrides):
        base = {
            "pl_name": "NO GEOM PLANET b",
            "pl_orbper": 4.0,
            "pl_orbsmax": np.nan,
            "st_mass": np.nan,   # a cannot be derived from Kepler either
            "st_rad": np.nan,
            "pl_orbeccen": np.nan,
            "pl_orblper": np.nan,
            "pl_rade": np.nan,
            "pl_trandur": np.nan,
        }
        base.update(overrides)
        return pd.Series(base)

    def test_default_2h_fallback_logs_a_warning(self, capsys):
        geom = sched.compute_transit_geometry(self._no_geometry_row())

        assert geom["t14_h"] == 2.0
        out = capsys.readouterr().out.lower()
        assert "2.0 h" in out
        assert "placeholder" in out

    def test_trandur_fallback_also_logs_attribution(self, capsys):
        row = self._no_geometry_row(pl_name="TRANDUR ONLY PLANET b",
                                     pl_trandur=3.5)

        geom = sched.compute_transit_geometry(row)

        assert geom["t14_h"] == 3.5
        out = capsys.readouterr().out.lower()
        assert "pl_trandur" in out

    def test_no_warning_when_geometry_is_resolvable(self, capsys):
        geom = sched.compute_transit_geometry(composite_row(pl_orbsmax=0.06356))

        assert np.isfinite(geom["t14_h"])
        out = capsys.readouterr().out.lower()
        assert "placeholder" not in out
        assert "does not transit" not in out
