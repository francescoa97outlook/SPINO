"""
On an orbit shorter than the night, the partial events of two consecutive
orbits must not add up to one fully covered event: each orbit is matched on
its own.
"""

import numpy as np
import pytest
import astropy.units as u
from astropy.time import Time

import phase_scheduler as sched

P_D = 0.45                            # 10.8 h, shorter than the 14 h grid
HALF_PH = 0.5 / 2 / (P_D * 24)        # a 0.5 h transit


def night_starting_at_phase(phase0, obs_until_h):
    t_h = np.arange(421) * 2 / 60.0   # 14 h at 2 min
    return {
        "has_obs": True,
        "phases": (phase0 + t_h / (P_D * 24)) % 1.0,
        "obs_mask": t_h <= obs_until_h + 1e-9,
        "times_utc": Time("2027-06-21T00:00:00") + t_h * u.hour,
        "target_alt": np.full(t_h.size, 45.0),
    }


def transit_windows():
    return {"transit": [(1.0 - HALF_PH, 1.0), (0.0, HALF_PH)]}


def test_two_half_transits_are_not_one_full_transit():
    # Starts at mid-transit, observable until the next mid-transit: half of
    # each of two transits is observable.
    night = night_starting_at_phase(0.0, obs_until_h=P_D * 24)

    events = sched.match_events(
        night, transit_windows(), {"transit": {"min_coverage": 1.0}}, {})

    assert events == []


def test_each_half_transit_is_its_own_event():
    night = night_starting_at_phase(0.0, obs_until_h=P_D * 24)

    events = sched.match_events(
        night, transit_windows(), {"transit": {"min_coverage": 0.4}}, {})

    assert len(events) == 2
    for e in events:
        assert e["coverage"] == pytest.approx(0.5, abs=0.02)
    assert events[0]["ut_end"] < events[1]["ut_start"]
    assert events[0]["_span"][1] < events[1]["_span"][0]


def test_one_full_and_one_partial_transit_give_one_full_event():
    # Mid-transit at 2 h is fully observable; the next one, at 12.8 h, is
    # cut at 12.8 h.
    phase0 = 1.0 - 2.0 / (P_D * 24)
    night = night_starting_at_phase(phase0, obs_until_h=12.8)

    events = sched.match_events(
        night, transit_windows(), {"transit": {"min_coverage": 1.0}}, {})

    assert len(events) == 1
    assert events[0]["coverage"] == pytest.approx(1.0)
    assert events[0]["ut_start"].startswith("2027-06-21 01:4")
