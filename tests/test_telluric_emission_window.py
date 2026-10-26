"""
For a pre- or post-eclipse event the planetary radial velocity of the telluric
page must be the one of the emission window, not of the nearest transit.

Expected planetary velocities are hand-computed from K_p*sin(2*pi*phi) at the
window phases of the synthetic events below.
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pytest
from astropy.time import Time

import phase_telluric_plot as tp

from test_telluric_drv import OBSERVATORY, PERIOD, T0, make_target

KP = 117.0
VSYS = 31.549

# The band edges are compared with K_p sin(2 pi phi) at the nominal phase
# limits: the first and last observed grid points sit up to ~0.8 km/s inside
# them, and v_bary drifts by up to ~0.6 km/s across the window around its
# mean.  The transit-phase band this replaces is off by over 50 km/s.
TOL = 1.5


def make_emission_event(event_type, window, observed):
    """A night sampling the phases of ``window`` (plus margins), observable
    only between the phases ``observed``; times are BJD_TDB-consistent."""
    n_orbit = 100
    lo, hi = window[0] - 0.05, window[1] + 0.05
    phases = np.linspace(lo, hi, 400)
    bjd = T0 + (n_orbit + phases) * PERIOD
    times_utc = Time(bjd, format="jd", scale="tdb").utc
    obs_mask = (phases >= observed[0]) & (phases <= observed[1])
    return {
        "event_type": event_type,
        "_night": {
            "times_utc": times_utc,
            "phases": phases % 1.0,
            "bjd_tdb": bjd,
            "obs_mask": obs_mask,
            "date_str": "2071-01-01",
        },
        "_windows": {event_type: [window]},
        "_geom": {"t14_h": 3.4, "phi_sec": 0.5, "half_ph_sec": 0.0145},
    }


def drv(event):
    target = make_target(ecc=None, kp_kms=KP)
    return tp.compute_planet_telluric_drv(
        event, OBSERVATORY, target, VSYS, KP, 3.4)


class TestPreEclipse:

    EVENT = dict(event_type="pre_eclipse", window=(0.25, 0.4855),
                 observed=(0.30, 0.40))

    def test_grid_samples_the_emission_window_not_the_transit(self):
        info = drv(make_emission_event(**self.EVENT))

        pad = 30.0 / (24.0 * 60.0) / PERIOD
        assert info["phase"].min() >= 0.25 - pad - 1e-9
        assert info["phase"].max() <= 0.4855 + pad + 1e-9

    def test_band_covers_the_observed_part_of_the_window(self):
        # K_p sin(2 pi 0.40) = 68.77, K_p sin(2 pi 0.30) = 111.27 km/s.
        info = drv(make_emission_event(**self.EVENT))

        frame = VSYS - float(np.mean(info["vbary"][info["observed"]]))
        assert info["min"] - frame == pytest.approx(68.77, abs=TOL)
        assert info["max"] - frame == pytest.approx(111.27, abs=TOL)


class TestPostEclipse:

    EVENT = dict(event_type="post_eclipse", window=(0.5145, 0.75),
                 observed=(0.60, 0.70))

    def test_band_covers_the_observed_part_of_the_window(self):
        # K_p sin(2 pi 0.70) = -111.27, K_p sin(2 pi 0.60) = -68.77 km/s.
        info = drv(make_emission_event(**self.EVENT))

        frame = VSYS - float(np.mean(info["vbary"][info["observed"]]))
        assert info["min"] - frame == pytest.approx(-111.27, abs=TOL)
        assert info["max"] - frame == pytest.approx(-68.77, abs=TOL)


class TestEmissionPageRendering:

    def test_phase_axis_is_the_orbital_phase(self, tmp_path):
        from test_telluric_plot_render import LAM_RANGE_NM, RV_GRID_KMS, SKY_FITS
        from matplotlib.backends.backend_pdf import PdfPages

        event = make_emission_event(**TestPreEclipse.EVENT)
        target = make_target(ecc=None, kp_kms=KP)
        with PdfPages(tmp_path / "page.pdf") as pdf:
            fig = tp.plot_telluric_position(
                event, OBSERVATORY, target, vsys_kms=VSYS,
                sky_fits_path=str(SKY_FITS), lam_range_nm=LAM_RANGE_NM,
                rv_grid_kms=RV_GRID_KMS, pad_hours=1.0, exp_time_s=300.0,
                pdf=pdf, kp_kms=KP,
            )

        assert "orbital phase" in fig.axes[1].get_ylabel().lower()
        labels = [t.get_text().lower()
                  for t in fig.axes[1].get_legend().get_texts()]
        assert any("pre-eclipse window" in s for s in labels)
