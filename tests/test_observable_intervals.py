"""
A night can contain two separate observable stretches, for instance when a
target near the pole dips below the altitude limit around lower culmination.
The phase interval between them is not observable and must not count towards
the coverage of an event.
"""

import numpy as np
import pytest

import phase_scheduler as sched


def test_two_observable_stretches_give_two_intervals():
    phases = np.linspace(0.10, 0.40, 301)          # step 0.001
    obs_mask = np.zeros(301, dtype=bool)
    obs_mask[:51] = True                            # 0.100 .. 0.150
    obs_mask[250:] = True                           # 0.350 .. 0.400

    intervals = sched._observable_stretches(
        sched._unwrapped_phase(phases), obs_mask)

    assert len(intervals) == 2
    assert intervals[0] == pytest.approx((0.10, 0.15))
    assert intervals[1] == pytest.approx((0.35, 0.40))


def test_an_event_spanning_the_gap_is_not_covered():
    # Window 0.14-0.36: only 0.14-0.15 and 0.35-0.36 are observable, a
    # coverage of 0.02/0.22 = 0.09, well below the 0.5 required.
    from astropy.time import Time
    import astropy.units as u

    phases = np.linspace(0.10, 0.40, 301)
    obs_mask = np.zeros(301, dtype=bool)
    obs_mask[:51] = True
    obs_mask[250:] = True
    night = {
        "has_obs": True, "phases": phases, "obs_mask": obs_mask,
        "times_utc": Time("2027-06-21T00:00:00") + np.arange(301) * 2 * u.min,
        "target_alt": np.full(301, 45.0),
    }
    windows = {"transit": [], "pre_eclipse": [(0.14, 0.36)], "post_eclipse": []}

    events = sched.match_events(
        night, windows, {"pre_eclipse": {"min_coverage": 0.5}}, geom={})

    assert events == []


def test_a_wrap_through_phase_zero_inside_one_stretch_stays_continuous():
    phases = np.concatenate([np.linspace(0.95, 0.999, 50),
                             np.linspace(0.0, 0.05, 51)])
    obs_mask = np.ones(phases.size, dtype=bool)

    intervals = sched._observable_stretches(
        sched._unwrapped_phase(phases), obs_mask)

    assert len(intervals) == 1
    assert intervals[0] == pytest.approx((0.95, 1.05))
