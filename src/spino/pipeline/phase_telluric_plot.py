"""
Telluric Position Plot
======================
Adds a per-event diagnostic page to the phase scheduler's per-event PDFs.

For each scheduled event, the plot replicates `plot_telluric_position.ipynb`:
  • Earth-frame: cross-correlation of the GIANO-B sky transmission spectrum
    with itself over an RV grid (peak at 0 km/s).
  • Stellar-frame: same CC curve shifted by  vtot = vsys − ⟨vbary⟩,
    showing where telluric features land in the stellar rest frame.

Synthetic exposures (1 h before window start → 1 h after window end at 300 s
cadence) are generated to estimate ⟨vbary⟩ via astropy's
`SkyCoord.radial_velocity_correction`.
"""

from __future__ import annotations
from functools import lru_cache
import os
import warnings

import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation
import astropy.units as u
from scipy.interpolate import InterpolatedUnivariateSpline
import matplotlib.pyplot as plt

from phase_plotter import _phase_in_windows, _EVENT_COLORS

CLIGHT_KMS = 2.997e5

_warned_planets: set[str] = set()


def _warn_once(planet_name: str, msg: str) -> None:
    key = f"{planet_name}::{msg}"
    if key in _warned_planets:
        return
    _warned_planets.add(key)
    print(f"[telluric] {msg}")


def compute_synthetic_exposure_times(event, exp_time_s=300.0, pad_hours=1.0):
    """
    Locate the in-event time interval and return a uniform Time grid sampling
    [t_start − pad, t_end + pad] every `exp_time_s` seconds.

    Returns
    -------
    times : astropy.time.Time
        UTC times of the synthetic exposure midpoints.
    """
    night = event["_night"]
    windows = event["_windows"]
    event_type = event["event_type"]

    times_utc = night["times_utc"]
    phases = np.asarray(night["phases"], dtype=float)

    in_event = _phase_in_windows(phases, windows.get(event_type, []))
    idx = np.where(in_event)[0]
    if idx.size == 0:
        return None

    t_start_jd = times_utc[idx[0]].jd
    t_end_jd = times_utc[idx[-1]].jd

    pad_days = pad_hours / 24.0
    exp_days = exp_time_s / 86400.0
    grid_jd = np.arange(
        t_start_jd - pad_days,
        t_end_jd + pad_days + 0.5 * exp_days,
        exp_days,
    )
    return Time(grid_jd, format="jd", scale="utc")


def compute_planet_telluric_drv(event, observatory, target, vsys_kms, kp_kms,
                                t14_h, pad_min=30.0, step_s=200.0):
    """
    Sample the planet–telluric RV difference on a fine time grid spanning
    [T₁ − pad, T₄ + pad] with ``step_s`` cadence.

    Tellurics sit at 0 km/s in the Earth frame, so:
        ΔRV(t) = V_p(t) − 0 = V_sys + K_p·sin(2π·φ(t)) − V_bary(t)

    The midpoint of the transit is reconstructed from the linear ephemeris
    (T₀, P) by picking the orbit number whose predicted midpoint sits
    closest to the centre of the observable window of ``event``.  This
    means the grid covers the whole transit even when the observable
    window only captures part of it.

    Returns
    -------
    dict | None
        ``t_min_from_mid`` (minutes from T_mid), ``bjd_tdb`` (JD_TDB, no
        light-travel correction - same convention as the existing plot),
        ``phase``, ``vbary`` (km/s), ``v_planet`` (km/s), ``drv`` (km/s,
        ≡ v_planet), plus scalar stats ``mean``, ``min``, ``max``,
        ``span`` and the reference values ``t_mid_bjd_tdb`` and ``t14_h``.
        ``None`` when inputs are insufficient.
    """
    t0_bjd = target.get("t0_bjd")
    period = target.get("period")
    if (t0_bjd is None or period is None
            or kp_kms is None or not np.isfinite(kp_kms)
            or t14_h is None or not np.isfinite(t14_h)):
        return None

    night = event["_night"]
    times_utc_night = night["times_utc"]
    phases_night = np.asarray(night["phases"], dtype=float)
    in_event = _phase_in_windows(
        phases_night, event["_windows"].get(event["event_type"], []),
    )
    idx = np.where(in_event)[0]
    if idx.size == 0:
        return None

    # Anchor the transit midpoint to the ephemeris orbit nearest the window.
    t_mid_jd_utc = 0.5 * (times_utc_night[idx[0]].jd
                          + times_utc_night[idx[-1]].jd)
    t_mid_jd_tdb_approx = Time(t_mid_jd_utc, format="jd", scale="utc").tdb.jd
    n_orbit = round((t_mid_jd_tdb_approx - float(t0_bjd)) / float(period))
    t_mid_bjd = float(t0_bjd) + n_orbit * float(period)

    t14_d  = float(t14_h) / 24.0
    pad_d  = float(pad_min) / (24.0 * 60.0)
    step_d = float(step_s) / 86400.0
    t1_bjd = t_mid_bjd - 0.5 * t14_d - pad_d
    t4_bjd = t_mid_bjd + 0.5 * t14_d + pad_d
    grid_bjd = np.arange(t1_bjd, t4_bjd + 0.5 * step_d, step_d)

    # Convert JD_TDB → UTC for the barycentric correction (TDB↔UTC offset
    # only; the ~8 min barycentric light-travel-time term is ignored, in
    # line with phase_telluric_plot.compute_synthetic_exposure_times which
    # uses times_utc.tdb.jd directly).
    grid_utc = Time(grid_bjd, format="jd", scale="tdb").utc

    vbary = compute_barycentric_velocity(
        grid_utc,
        ra_deg=target["ra_deg"], dec_deg=target["dec_deg"],
        lat_deg=observatory["lat"], lon_deg=observatory["lon"],
        alt_m=observatory["alt"],
    )
    phase = (grid_bjd - float(t0_bjd)) / float(period)
    phase = phase - np.floor(phase)
    v_planet = (float(vsys_kms)
                + float(kp_kms) * np.sin(2.0 * np.pi * phase)
                - vbary)
    drv = v_planet   # tellurics anchored at 0 km/s in the Earth frame

    return dict(
        t_min_from_mid=(grid_bjd - t_mid_bjd) * 24.0 * 60.0,
        bjd_tdb=grid_bjd,
        phase=phase,
        vbary=vbary,
        v_planet=v_planet,
        drv=drv,
        mean=float(np.mean(drv)),
        min=float(np.min(drv)),
        max=float(np.max(drv)),
        span=float(np.max(drv) - np.min(drv)),
        t_mid_bjd_tdb=t_mid_bjd,
        t14_h=float(t14_h),
    )


def compute_barycentric_velocity(times_utc, ra_deg, dec_deg,
                                 lat_deg, lon_deg, alt_m):
    """
    Barycentric velocity correction [km/s] at each UTC time.

    Uses `SkyCoord.radial_velocity_correction('barycentric', ...)`, which
    returns the velocity at which the observer is moving toward the target in
    the barycentric frame - the modern, canonical equivalent of the IDL
    `helcorr` and the user's hand-rolled `helcorr_velocity`.
    """
    location = EarthLocation.from_geodetic(
        lon=lon_deg * u.deg, lat=lat_deg * u.deg, height=alt_m * u.m,
    )
    target = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    vbary = target.radial_velocity_correction(
        kind="barycentric", obstime=times_utc, location=location,
    )
    return vbary.to(u.km / u.s).value


@lru_cache(maxsize=8)
def load_telluric_model(fits_path: str, lam_min_nm: float, lam_max_nm: float):
    """
    Load and slice the GIANO-B sky-transmission FITS file.

    The FITS HDU 1 has a binary table with columns 'lam' (microns) and
    'trans'. We convert wavelengths to nm and restrict to the requested
    range. Cached on (path, range).
    """
    with fits.open(fits_path) as hdul:
        d = hdul[1].data
        lam_nm = np.asarray(d["lam"], dtype=np.float64) * 1e3
        trans = np.asarray(d["trans"], dtype=np.float64)
    mask = (lam_nm >= lam_min_nm) & (lam_nm <= lam_max_nm)
    return lam_nm[mask], trans[mask]


@lru_cache(maxsize=8)
def _earth_frame_cc_cached(fits_path, lam_range_nm, rv_grid_kms):
    """
    Earth-frame CC: cross-correlate the telluric spectrum with itself over
    `rv_grid_kms`. Cached, so this runs once per scheduler invocation.

    Returns (rv_array, ccor_earth, lar, far).
    """
    lar, far = load_telluric_model(fits_path, lam_range_nm[0], lam_range_nm[1])
    rv_start, rv_stop_inclusive, rv_step = rv_grid_kms
    rv = np.arange(rv_start, rv_stop_inclusive + 0.5 * rv_step, rv_step)

    spline_spec = InterpolatedUnivariateSpline(lar, far, k=3, ext=0)
    ccor = np.zeros_like(rv)
    far_norm = np.sum(far ** 2)
    for j, vshift in enumerate(rv):
        lars = lar * (1.0 + vshift / CLIGHT_KMS)
        fars = spline_spec(lars)
        ccor[j] = np.sum(far * fars) / np.sqrt(far_norm * np.sum(fars ** 2))
    return rv, ccor, lar, far


def plot_telluric_position(event, obs, target, vsys_kms, sky_fits_path,
                           lam_range_nm, rv_grid_kms, pad_hours, exp_time_s,
                           pdf, kp_kms=None):
    """
    Append one telluric-position page to `pdf` for the given event.

    When ``kp_kms`` is finite, an additional vertical band marks the planet's
    expected RV trace ``Kp · sin(2π·φ)`` evaluated at the synthetic-exposure
    phases of the event - i.e. the range of stellar-rest-frame velocities the
    planet's signal will sweep through during the observation.

    Skips silently (with a one-shot warning) when:
      • vsys_kms is None,
      • sky_fits_path is empty/missing,
      • event has no in-window samples (degenerate case).
    """
    name = target.get("name", "?")

    if vsys_kms is None or not np.isfinite(vsys_kms):
        _warn_once(name, f"skipped {name}: vsys unavailable")
        return
    if not sky_fits_path or not os.path.exists(sky_fits_path):
        _warn_once(name, f"skipped {name}: sky_transmission FITS not found "
                         f"at {sky_fits_path!r}")
        return

    times_utc = compute_synthetic_exposure_times(
        event, exp_time_s=exp_time_s, pad_hours=pad_hours,
    )
    if times_utc is None or len(times_utc) == 0:
        _warn_once(name, f"skipped {name}: empty in-event window")
        return

    vbary = compute_barycentric_velocity(
        times_utc,
        ra_deg=target["ra_deg"], dec_deg=target["dec_deg"],
        lat_deg=obs["lat"], lon_deg=obs["lon"], alt_m=obs["alt"],
    )
    vbary_mean = float(np.mean(vbary))
    vtot = float(vsys_kms) - vbary_mean

    try:
        rv, ccor_earth, _lar, _far = _earth_frame_cc_cached(
            sky_fits_path, tuple(lam_range_nm), tuple(rv_grid_kms),
        )
    except Exception as exc:
        _warn_once(name, f"skipped {name}: telluric CC failed ({exc})")
        return

    spline_cc = InterpolatedUnivariateSpline(rv, ccor_earth, k=3, ext=3)
    # Star in Earth frame: telluric CC shape shifted so its peak lands at
    # vtot = Vsys − <Vbary> - i.e. where stellar lines fall when observed
    # from Earth.  All quantities on this plot stay in the Earth frame.
    ccor_star = spline_cc(rv - vtot)

    bjd_tdb = times_utc.tdb.jd
    n_exp = len(times_utc)
    bjd_start, bjd_end = bjd_tdb.min(), bjd_tdb.max()
    span_h = (bjd_end - bjd_start) * 24.0

    event_type = event["event_type"]
    date_str = event["_night"]["date_str"]
    color = _EVENT_COLORS.get(event_type, "#4169E1")

    # Fine-grained planet–telluric ΔRV grid (T₁−30min → T₄+30min, 200s step)
    geom = event.get("_geom") or {}
    t14_h = geom.get("t14_h")
    drv_info = compute_planet_telluric_drv(
        event, obs, target, vsys_kms, kp_kms, t14_h,
        pad_min=30.0, step_s=200.0,
    )

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(16, 6),
        gridspec_kw=dict(width_ratios=[3, 2.2]),
    )
    ax.plot(rv, ccor_earth, color="k", linestyle="-", lw=1.6,
            label="Telluric (Earth frame)")
    ax.plot(rv, ccor_star, color=color, linestyle=":", lw=2.0,
            label=f"Star (Earth frame, $v_\\star$ = {vtot:+.2f} km/s)")

    ax.axvline(0.0, color="gray", lw=0.6, ls=":", alpha=0.7)
    ax.axvline(vtot, color=color, lw=0.6, ls=":", alpha=0.7)

    # Planet RV band in the Earth/telluric frame.
    # The band uses the same ΔRV grid as the right subplot
    # ([T₁ − 30 min, T₄ + 30 min], 200 s step) so the two panels are
    # directly comparable.  Falls back to the synthetic-exposure grid when
    # the geometry needed by `compute_planet_telluric_drv` is missing.
    kp_band = None
    if drv_info is not None:
        rv_p_min, rv_p_max = drv_info["min"], drv_info["max"]
        ax.axvspan(rv_p_min, rv_p_max, color="#FF8C00", alpha=0.18,
                   zorder=1,
                   label=r"Planet RV $V_{\rm sys}+K_p\sin(2\pi\varphi)"
                         r"-V_{\rm bary}$  (T$_1$−30→T$_4$+30)")
        if rv_p_max - rv_p_min < 0.5:  # nearly a line
            ax.axvline(0.5 * (rv_p_min + rv_p_max), color="#FF8C00",
                       lw=1.0, alpha=0.8)
        kp_band = (rv_p_min, rv_p_max)
    elif kp_kms is not None and np.isfinite(kp_kms) and target.get("t0_bjd") \
            and target.get("period"):
        # Fallback: synthetic-exposure grid (no geom available)
        phases_exp = ((bjd_tdb - float(target["t0_bjd"]))
                      / float(target["period"]))
        phases_exp = phases_exp - np.floor(phases_exp)
        rv_planet = (float(vsys_kms)
                     + float(kp_kms) * np.sin(2.0 * np.pi * phases_exp)
                     - vbary)
        rv_p_min, rv_p_max = float(rv_planet.min()), float(rv_planet.max())
        ax.axvspan(rv_p_min, rv_p_max, color="#FF8C00", alpha=0.18,
                   zorder=1,
                   label=r"Planet RV $V_{\rm sys}+K_p\sin(2\pi\varphi)"
                         r"-V_{\rm bary}$  (obs. window)")
        if rv_p_max - rv_p_min < 0.5:
            ax.axvline(0.5 * (rv_p_min + rv_p_max), color="#FF8C00",
                       lw=1.0, alpha=0.8)
        kp_band = (rv_p_min, rv_p_max)

    ax.set_xlim(rv.min(), rv.max())
    ax.set_ylim(0.95, 1.03)
    ax.set_xlabel("RV [km/s]")
    ax.set_ylabel("Normalized cross-correlation")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=10)

    ax.set_title(
        f"Telluric position - {name} - "
        f"{event_type.replace('_', ' ').title()} - {date_str}",
        fontsize=13, pad=10,
    )

    # Right subplot: ΔRV(φ) = V_planet − V_telluric across the transit.
    # X = ΔRV [km/s], Y = orbital phase (unwrapped around the transit so
    # that values just below φ=1 map onto small negative phases instead of
    # jumping discontinuously).
    if drv_info is not None:
        drv = drv_info["drv"]
        phase_plot = np.where(drv_info["phase"] > 0.5,
                              drv_info["phase"] - 1.0,
                              drv_info["phase"])
        period_d = float(target["period"])
        dphi_t14 = (drv_info["t14_h"] / 24.0) / period_d
        phi_t1, phi_t4 = -0.5 * dphi_t14, +0.5 * dphi_t14
        ax2.plot(drv, phase_plot, color="#FF8C00", lw=1.4,
                 marker="o", ms=2.6, mfc="#FF8C00", mec="none",
                 label=r"$\Delta\mathrm{RV}(\varphi)$")
        ax2.axhspan(phi_t1, phi_t4, color=color, alpha=0.08,
                    label=r"$T_{14}$")
        ax2.axhline(0.0,    color="gray", lw=0.6, ls=":", alpha=0.7)
        ax2.axhline(phi_t1, color=color, lw=0.6, ls="--", alpha=0.5)
        ax2.axhline(phi_t4, color=color, lw=0.6, ls="--", alpha=0.5)
        ax2.axvline(0.0, color="k", lw=0.5, alpha=0.4)
        ax2.set_xlabel(r"$\Delta\mathrm{RV}_{\rm planet-telluric}$ [km/s]")
        ax2.set_ylabel(r"Orbital phase $\varphi$")
        ax2.set_title(
            r"$\langle\Delta v\rangle$ = "
            f"{drv_info['mean']:+.2f} km/s,  range "
            f"[{drv_info['min']:+.2f}, {drv_info['max']:+.2f}]  "
            f"(step 200s)",
            fontsize=11, pad=8,
        )
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="best", fontsize=9)
    else:
        ax2.axis("off")
        ax2.text(0.5, 0.5,
                 r"$\Delta$RV grid unavailable" "\n"
                 "(missing Kp / T₁₄ / ephemeris)",
                 ha="center", va="center", transform=ax2.transAxes,
                 fontsize=11, color="gray")

    if kp_band is not None:
        kp_line = (
            f"$K_p$ = {float(kp_kms):.2f} km/s; "
            f"planet RV $\\in$ "
            f"[{kp_band[0]:+.2f}, {kp_band[1]:+.2f}] km/s\n"
        )
    elif kp_kms is None or not np.isfinite(kp_kms):
        kp_line = "$K_p$: not available\n"
    else:
        kp_line = ""

    if drv_info is not None:
        drv_line = (
            r"$\langle\Delta v\rangle_{\rm planet-tell}$"
            f" = {drv_info['mean']:+.2f} km/s; "
            f"range [{drv_info['min']:+.2f}, {drv_info['max']:+.2f}], "
            f"span {drv_info['span']:.2f} km/s "
            f"(T$_1$−30min → T$_4$+30min, 200s step)\n"
        )
    else:
        drv_line = ""

    info = (
        f"$v_{{\\rm sys}}$ = {vsys_kms:+.3f} km/s\n"
        f"$\\langle v_{{\\rm bary}}\\rangle$ = {vbary_mean:+.3f} km/s\n"
        f"$v_\\star = v_{{\\rm sys}} - \\langle v_{{\\rm bary}}\\rangle$ "
        f"= {vtot:+.3f} km/s  (star in Earth frame)\n"
        + kp_line
        + drv_line +
        f"$n_{{\\rm exp}}$ = {n_exp}  ({exp_time_s:.0f}s cadence, "
        f"span {span_h:.2f} h)\n"
        f"BJD$_{{\\rm TDB}}$: {bjd_start:.5f} → {bjd_end:.5f}\n"
        f"$\\lambda$ range: {lam_range_nm[0]:.0f}–{lam_range_nm[1]:.0f} nm "
        f"(GIANO-B order zero)"
    )
    ax.text(
        0.02, 0.02, info, transform=ax.transAxes,
        ha="left", va="bottom", fontsize=8.5, family="monospace",
        bbox=dict(boxstyle="round,pad=0.5",
                  facecolor="white", edgecolor="#bbbbbb", alpha=0.9),
    )

    fig.tight_layout()
    pdf.savefig(fig, dpi=150, bbox_inches="tight")
    plt.close(fig)
