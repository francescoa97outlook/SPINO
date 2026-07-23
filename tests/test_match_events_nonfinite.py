"""
Before this fix, a non-finite transit window (e.g. from an unresolved,
non-transiting composite geometry -- see test_transit_geometry_nontransiting)
turned into 338 false transit events for HD 219666 b instead of zero: every
NaN comparison in match_events evaluates to False, so `evt_width <= 0`,
`coverage < min_cov`, and the wrap-around branch `s <= e` in the in-event
mask all took the "pass" side, and `(phases >= NaN) | (phases <= 1.0)`
matched the entire night.

This is the test that matters most in this batch: without it, the defect
shows up as 338 plausible-looking events instead of an outright error.
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pytest
import astropy.units as u
from astropy.time import Time

import phase_scheduler as sched


def _fully_observable_night(n=50):
    phases = np.linspace(0.0, 0.999, n)
    times_utc = Time("2027-05-02T00:00:00") + np.arange(n) * 0.2 * u.hour
    return {
        "has_obs": True,
        "phases": phases,
        "obs_mask": np.ones(n, dtype=bool),
        "times_utc": times_utc,
        "target_alt": np.full(n, 45.0),
    }


class TestComputeEventWindowsWithNonFiniteGeometry:

    def test_nonfinite_half_ph_yields_no_transit_window(self):
        geom = {
            "half_ph": np.nan, "phi_sec": 0.5, "half_ph_sec": np.nan,
        }

        windows = sched.compute_event_windows(geom)

        assert windows["transit"] == []

    def test_nonfinite_phi_sec_yields_no_eclipse_windows(self):
        geom = {
            "half_ph": 0.01, "phi_sec": np.nan, "half_ph_sec": np.nan,
        }

        windows = sched.compute_event_windows(geom)

        assert windows["pre_eclipse"] == []
        assert windows["post_eclipse"] == []
        # A finite half_ph still produces a real transit window; the two
        # kinds of window must fail independently.
        assert windows["transit"] != []

    def test_finite_geometry_is_unaffected(self):
        geom = {"half_ph": 0.0082, "phi_sec": 0.4681, "half_ph_sec": 0.0082}

        windows = sched.compute_event_windows(geom)

        assert windows["transit"] == [(1.0 - 0.0082, 1.0), (0.0, 0.0082)]


class TestMatchEventsRejectsNonFiniteWindows:

    def test_nan_transit_window_from_geometry_produces_zero_events(self):
        # The exact HD 219666 b regression: an unresolved (non-transiting)
        # composite geometry, run through the real compute_event_windows,
        # against a night where literally everything is observable.
        geom_nan = {"half_ph": np.nan, "phi_sec": np.nan, "half_ph_sec": np.nan}
        windows = sched.compute_event_windows(geom_nan)
        night = _fully_observable_night()

        events = sched.match_events(
            night, windows,
            {"transit": {"min_coverage": 1.0}}, geom_nan,
        )

        assert events == []

    def test_directly_nan_bounded_window_is_also_rejected(self):
        # Belt-and-braces: even if some other geometry source ever hands
        # match_events a window with NaN bounds directly (bypassing
        # compute_event_windows' own filtering), it must not match.
        night = _fully_observable_night()
        windows = {"transit": [(np.nan, 1.0), (0.0, np.nan)]}

        events = sched.match_events(
            night, windows, {"transit": {"min_coverage": 1.0}}, {},
        )

        assert events == []

    def test_finite_window_still_matches_normally(self):
        # Regression guard: the guard added for NaN must not reject a
        # perfectly normal, finite, fully-covered transit window.  Kept
        # well inside [0, 0.999] (the observable night's phase range) so
        # coverage is exactly 1.0, not a wrap-around edge case.
        night = _fully_observable_night()
        windows = {"transit": [(0.40, 0.42)]}

        events = sched.match_events(
            night, windows, {"transit": {"min_coverage": 1.0}}, {},
        )

        assert len(events) == 1
        assert events[0]["event_type"] == "transit"
        assert events[0]["coverage"] == pytest.approx(1.0)
