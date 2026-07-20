"""
Integration test for the planet-telluric DeltaRV grid.

Exercises the real `compute_planet_telluric_drv` (real astropy barycentric
correction, no mocks) on a synthetic event, to check the wiring between the
orbital solution and the telluric frame.
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pytest
from astropy.time import Time

import phase_kepler as pk
import phase_telluric_plot as tp


PERIOD = 4.8878
T0 = 2458000.0
T14_H = 3.4

OBSERVATORY = dict(lat=-24.6272, lon=-70.4045, alt=2635.0)   # Paranal


def make_target(ecc=None, omega_p_deg=None, kp_kms=117.0):
    return dict(
        name="TEST b",
        ra_deg=190.152, dec_deg=-19.2844,
        period=PERIOD, t0_bjd=T0,
        v_sys_kms=31.549, kp_kms=kp_kms,
        ecc=ecc, omega_p_deg=omega_p_deg,
    )


def make_event():
    """An event whose observable window brackets a mid-transit at T0 + 100 P."""
    t_mid_tdb = T0 + 100 * PERIOD
    half = (T14_H / 24.0) / 2.0
    times_tdb = np.linspace(t_mid_tdb - 2 * half, t_mid_tdb + 2 * half, 41)
    times_utc = Time(times_tdb, format="jd", scale="tdb").utc

    phases = (times_tdb - T0) / PERIOD
    phases = phases - np.floor(phases)
    dphi = half / PERIOD

    return {
        "event_type": "transit",
        "_night": {
            "times_utc": times_utc,
            "phases": phases,
            "date_str": "2071-01-01",
        },
        "_windows": {"transit": [(1.0 - dphi, dphi)]},
        "_geom": {"t14_h": T14_H},
    }


class TestCircularTargetIsUnchanged:

    def test_drv_equals_the_legacy_expression(self):
        target = make_target(ecc=None)
        info = tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY, target,
            target["v_sys_kms"], target["kp_kms"], T14_H,
        )

        assert info is not None
        expected = (target["v_sys_kms"]
                    + target["kp_kms"] * np.sin(2.0 * np.pi * info["phase"])
                    - info["vbary"])
        assert np.allclose(info["drv"], expected, atol=1e-6)

    def test_reports_circular_mode_and_no_deviation(self):
        info = tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY, make_target(ecc=0.0),
            31.549, 117.0, T14_H,
        )

        assert info["mode"] == "circular"
        assert info["max_dev_circ"] == pytest.approx(0.0, abs=1e-6)
        assert info["drv_lo"] is None and info["drv_hi"] is None


class TestEccentricTargetWithKnownOmega:

    def test_drv_follows_the_keplerian_trace(self):
        target = make_target(ecc=0.218, omega_p_deg=18.0)
        info = tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY, target, 31.549, 117.0, T14_H,
        )

        assert info["mode"] == "keplerian"
        expected = (31.549
                    + pk.planet_rv_kms(info["bjd_tdb"], T0, PERIOD, 0.218,
                                       18.0, pk.kp_eccentric(117.0, 0.218))
                    - info["vbary"])
        assert np.allclose(info["drv"], expected, atol=1e-6)

    def test_circular_reference_is_kept_alongside(self):
        info = tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY,
            make_target(ecc=0.218, omega_p_deg=18.0), 31.549, 117.0, T14_H,
        )

        expected = (31.549
                    + 117.0 * np.sin(2.0 * np.pi * info["phase"])
                    - info["vbary"])
        assert np.allclose(info["drv_circ"], expected, atol=1e-6)

    def test_deviation_from_circular_is_reported_and_large(self):
        info = tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY,
            make_target(ecc=0.218, omega_p_deg=18.0), 31.549, 117.0, T14_H,
        )

        assert info["max_dev_circ"] > 1.0
        assert info["max_dev_circ"] == pytest.approx(
            float(np.max(np.abs(info["drv"] - info["drv_circ"]))),
        )


class TestEccentricTargetWithUnknownOmega:

    def test_envelope_is_produced_and_brackets_the_trace(self):
        info = tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY,
            make_target(ecc=0.218, omega_p_deg=None), 31.549, 117.0, T14_H,
        )

        assert info["mode"] == "envelope"
        assert info["omega_used"] is None
        assert np.all(info["drv_lo"] <= info["drv"] + 1e-9)
        assert np.all(info["drv_hi"] >= info["drv"] - 1e-9)

    def test_min_max_span_cover_the_envelope_not_just_the_line(self):
        """The left panel's overlap band must reflect the full uncertainty."""
        info = tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY,
            make_target(ecc=0.218, omega_p_deg=None), 31.549, 117.0, T14_H,
        )

        assert info["min"] == pytest.approx(float(np.min(info["drv_lo"])))
        assert info["max"] == pytest.approx(float(np.max(info["drv_hi"])))


class TestRunLog:
    """The spec requires the run log to state the treatment for every target."""

    def setup_method(self):
        tp._warned_planets.clear()

    def test_reports_the_omega_used(self, capsys):
        tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY,
            make_target(ecc=0.218, omega_p_deg=18.0), 31.549, 117.0, T14_H,
        )

        out = capsys.readouterr().out
        assert "keplerian" in out.lower()
        assert "18.0" in out

    def test_reports_the_envelope_when_omega_is_unknown(self, capsys):
        tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY,
            make_target(ecc=0.218, omega_p_deg=None), 31.549, 117.0, T14_H,
        )

        out = capsys.readouterr().out
        assert "envelope" in out.lower()

    def test_stays_quiet_after_the_first_time(self, capsys):
        for _ in range(3):
            tp.compute_planet_telluric_drv(
                make_event(), OBSERVATORY,
                make_target(ecc=0.218, omega_p_deg=18.0), 31.549, 117.0, T14_H,
            )

        out = capsys.readouterr().out
        assert out.lower().count("keplerian") == 1


class TestMissingInputs:

    def test_returns_none_without_kp(self):
        assert tp.compute_planet_telluric_drv(
            make_event(), OBSERVATORY, make_target(), 31.549, None, T14_H,
        ) is None
