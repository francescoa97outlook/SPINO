"""
An eccentric orbit with an unknown argument of periastron must not be given a
silent omega = 0: T14 and phi_sec both depend on it, so the assumption has to
reach the run log.
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

import phase_scheduler as sched


def row(ecc=None, omega=None):
    return pd.Series({
        "pl_name": "TEST b",
        "pl_orbper": 4.8878,
        "pl_orbeccen": ecc if ecc is not None else np.nan,
        "pl_orblper": omega if omega is not None else np.nan,
        "pl_orbsmax": 0.0530,
        "st_rad": 0.75,
        "pl_rade": 4.36,
        "st_mass": 0.81,
        "pl_orbincl": 89.0,
        "pl_trandur": np.nan,
    })


@pytest.fixture(autouse=True)
def _reset_warnings():
    sched._geom_omega_warned.clear()
    yield


class TestEccentricWithUnknownOmega:

    def test_warns_that_omega_was_assumed(self, capsys):
        sched.compute_transit_geometry(row(ecc=0.218, omega=None))

        out = capsys.readouterr().out.lower()
        assert "omega" in out
        assert "0.218" in out

    def test_warns_only_once_per_target(self, capsys):
        for _ in range(3):
            sched.compute_transit_geometry(row(ecc=0.218, omega=None))

        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
        assert len(lines) == 1

    def test_geometry_is_still_produced(self):
        geom = sched.compute_transit_geometry(row(ecc=0.218, omega=None))

        assert geom is not None
        assert np.isfinite(geom["t14_h"])


class TestQuietCases:

    def test_circular_orbit_does_not_warn(self, capsys):
        sched.compute_transit_geometry(row(ecc=0.0, omega=None))

        assert "omega" not in capsys.readouterr().out.lower()

    def test_missing_eccentricity_does_not_warn(self, capsys):
        sched.compute_transit_geometry(row(ecc=None, omega=None))

        assert "omega" not in capsys.readouterr().out.lower()

    def test_known_omega_does_not_warn(self, capsys):
        sched.compute_transit_geometry(row(ecc=0.218, omega=18.0))

        assert "omega" not in capsys.readouterr().out.lower()
