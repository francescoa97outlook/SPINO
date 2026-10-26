"""
Every fallback that the transit geometry takes must be recorded in geom_flags,
so that it reaches events_summary.csv instead of staying implicit.
"""

import numpy as np
import pandas as pd
import pytest

import phase_scheduler as sched


def row(**overrides):
    base = dict(pl_name="TEST b", pl_orbper=4.8878, pl_orbeccen=0.0,
                pl_orblper=np.nan, pl_orbsmax=0.0530, st_rad=0.75,
                pl_rade=4.36, st_mass=0.81, pl_orbincl=89.0, pl_trandur=np.nan)
    base.update(overrides)
    return pd.Series(base)


@pytest.fixture(autouse=True)
def _reset_warnings():
    sched._geom_omega_warned.clear()
    yield


def test_missing_inclination_is_flagged():
    geom = sched.compute_transit_geometry(row(pl_orbincl=np.nan))

    assert geom["b"] == 0.0
    assert "incl_assumed_90" in geom["geom_flags"]


def test_missing_planet_radius_is_flagged():
    geom = sched.compute_transit_geometry(row(pl_rade=np.nan))

    assert geom["k"] == pytest.approx(0.01)
    assert "k_assumed" in geom["geom_flags"]


def test_semi_major_axis_rebuilt_during_composition_is_flagged():
    composite = row()
    composite["_field_sources"] = {"pl_orbsmax": "Kepler's 3rd law"}

    geom = sched.compute_transit_geometry(composite)

    assert "a_from_kepler" in geom["geom_flags"]


def test_complete_inputs_raise_no_fallback_flag():
    composite = row()
    composite["_field_sources"] = {"pl_orbsmax": "Somebody et al. 2020"}

    geom = sched.compute_transit_geometry(composite)

    assert not {"incl_assumed_90", "k_assumed", "a_from_kepler"} & set(
        geom["geom_flags"])
