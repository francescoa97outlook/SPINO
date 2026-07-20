"""
Telluric Position Plot
======================
Adds a per-event diagnostic page to the phase scheduler's per-event PDFs.

Everything on the page is in the Earth frame, where tellurics sit at 0 km/s:
  • the telluric cross-correlation, i.e. the sky-transmission spectrum
    correlated with itself over an RV grid (peak at 0 km/s);
  • the same curve translated by  vtot = vsys − ⟨vbary⟩, which is where the
    stellar lines fall when observed from the ground;
  • the planetary RV, whose orbital solution comes from `phase_kepler`
    (circular, Keplerian, or an envelope over all ω when the argument of
    periastron is unknown), with the circular approximation drawn alongside
    it for comparison whenever the orbit is eccentric.

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

from phase_plotter import _phase_in_windows
import phase_kepler

CLIGHT_KMS = 2.997e5

# Separator between fields on one line of the info block under the panels.
SEP = "   |   "

# One colour, one meaning, across both panels.  Reusing a hue for two
# quantities is what made the figure unreadable at a glance: orange used to
# mean three things and blue meant both "the star" (a velocity) and "T14"
# (a time interval).
C_TELLURIC = "k"          # telluric cross-correlation, Earth frame
C_STAR     = "#4169E1"    # stellar cross-correlation
C_PLANET   = "#FF8C00"    # planetary RV: adopted solution, and its omega envelope
C_CIRCULAR = "#777777"    # the circular approximation, wherever it appears
C_T14      = "#A8C4D9"    # transit duration, a time span rather than a velocity
C_GUIDE    = "#AAAAAA"    # zero markers and other non-informative guides

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
        ΔRV(t) = V_p(t) − 0 = V_sys + V_p,orbit(t) − V_bary(t)

    ``V_p,orbit`` comes from `phase_kepler.orbit_solution`: the circular
    ``K_p·sin(2π·φ)`` for e below `phase_kepler.ECC_MIN`, the Keplerian trace
    when e and ω are both known, and the circular trace plus an envelope over
    all ω when e is known but ω is not.

    The midpoint of the transit is reconstructed from the linear ephemeris
    (T₀, P) by picking the orbit number whose predicted midpoint sits
    closest to the centre of the observable window of ``event``.  This
    means the grid covers the whole transit even when the observable
    window only captures part of it.

    Returns
    -------
    dict | None
        ``t_min_from_mid`` (minutes from T_mid), ``bjd_tdb`` (JD_TDB, no
        light-travel correction, same convention as the existing plot),
        ``phase``, ``vbary`` (km/s), ``v_planet`` (km/s), ``drv`` (km/s,
        ≡ v_planet), the circular reference ``drv_circ`` and, under an
        envelope, its bounds ``drv_lo``/``drv_hi`` (``None`` otherwise);
        the orbital metadata ``mode``, ``ecc``, ``omega_used``, ``kp_circ``,
        ``kp_ecc``, ``max_dev_circ``; plus scalar stats ``mean``, ``min``,
        ``max``, ``span`` and the reference values ``t_mid_bjd_tdb`` and
        ``t14_h``.  ``min``/``max``/``span`` cover the envelope when there is
        one, so the overlap band reflects the full uncertainty.
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

    # Orbital treatment: circular, Keplerian, or an envelope over all omega
    # when the catalogue gives an eccentricity but no argument of periastron.
    sol = phase_kepler.orbit_solution(
        grid_bjd, t0_bjd, period,
        target.get("ecc"), target.get("omega_p_deg"), kp_kms,
    )
    if sol is None:
        return None
    _warn_once(target.get("name", "?"),
               f"{target.get('name', '?')}: "
               f"{phase_kepler.describe_orbit_solution(sol)}")

    # Tellurics sit at 0 km/s in the Earth frame, so DeltaRV is just the
    # planet's velocity there.
    def _to_earth_frame(v_star_frame):
        return float(vsys_kms) + v_star_frame - vbary

    drv = _to_earth_frame(sol["v_adopted"])
    drv_circ = _to_earth_frame(sol["v_circ"])
    drv_lo = _to_earth_frame(sol["v_lo"]) if sol["v_lo"] is not None else None
    drv_hi = _to_earth_frame(sol["v_hi"]) if sol["v_hi"] is not None else None

    # The overlap band on the left panel must show the whole uncertainty, so
    # under an envelope it spans the envelope rather than the drawn line.
    lo_arr = drv if drv_lo is None else drv_lo
    hi_arr = drv if drv_hi is None else drv_hi

    return dict(
        t_min_from_mid=(grid_bjd - t_mid_bjd) * 24.0 * 60.0,
        bjd_tdb=grid_bjd,
        phase=phase,
        vbary=vbary,
        v_planet=drv,
        drv=drv,
        drv_circ=drv_circ,
        drv_lo=drv_lo,
        drv_hi=drv_hi,
        mode=sol["mode"],
        ecc=sol["ecc"],
        omega_used=sol["omega_used"],
        kp_circ=sol["kp_circ"],
        kp_ecc=sol["kp_ecc"],
        max_dev_circ=sol["max_dev_circ"],
        mean=float(np.mean(drv)),
        min=float(np.min(lo_arr)),
        max=float(np.max(hi_arr)),
        span=float(np.max(hi_arr) - np.min(lo_arr)),
        t_mid_bjd_tdb=t_mid_bjd,
        t14_h=float(t14_h),
    )


def compute_barycentric_velocity(times_utc, ra_deg, dec_deg,
                                 lat_deg, lon_deg, alt_m):
    """
    Barycentric velocity correction [km/s] at each UTC time.

    Uses `SkyCoord.radial_velocity_correction('barycentric', ...)`, which
    returns the velocity at which the observer is moving toward the target in
    the barycentric frame, the modern, canonical equivalent of the IDL
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


def _solution_label(drv_info) -> str:
    """
    Legend text for the adopted orbital solution.

    Used verbatim for both the band on the left panel and the trace on the
    right one, so the same quantity is never given two names in one figure.
    """
    if drv_info["mode"] == "keplerian":
        return (f"Planet RV, Keplerian (e = {drv_info['ecc']:.3f}, "
                f"$\\omega_p$ = {drv_info['omega_used']:.0f}$^\\circ$)")
    if drv_info["mode"] == "envelope":
        return f"Planet RV, all $\\omega$ (e = {drv_info['ecc']:.3f})"
    return "Planet RV, circular"


def plot_telluric_position(event, obs, target, vsys_kms, sky_fits_path,
                           lam_range_nm, rv_grid_kms, pad_hours, exp_time_s,
                           pdf, kp_kms=None, drv_pad_min=30.0,
                           drv_step_s=200.0):
    """
    Append one telluric-position page to `pdf` for the given event.

    When ``kp_kms`` is finite, an additional vertical band marks the range of
    velocities the planet's signal sweeps through during the observation.  The
    trace behind that band comes from `phase_kepler.orbit_solution`, so for an
    eccentric orbit it is Keplerian rather than ``Kp · sin(2π·φ)``; the
    circular approximation is then overlaid for comparison, and an ω envelope
    is shown when the catalogue gives no argument of periastron.

    Returns the figure (already written to ``pdf`` and closed), or ``None``
    when the page was skipped.

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

    # Star in Earth frame: the telluric CC shape shifted so its peak lands at
    # vtot = Vsys − <Vbary>, i.e. where stellar lines fall when observed
    # from Earth.  All quantities on this plot stay in the Earth frame.
    #
    # The shift is applied to the abscissa, not by resampling the ordinate:
    # interpolating onto `rv - vtot` only covered the overlap between the grid
    # and its shifted copy, so once |vtot| approached the grid half-width the
    # peak fell outside the sampled range and scipy's ext=3 filled the rest
    # with a flat boundary value.  Translating the axis is exact for any vtot.
    rv_star = rv + vtot

    bjd_tdb = times_utc.tdb.jd
    n_exp = len(times_utc)
    bjd_start, bjd_end = bjd_tdb.min(), bjd_tdb.max()
    span_h = (bjd_end - bjd_start) * 24.0

    event_type = event["event_type"]
    date_str = event["_night"]["date_str"]

    # Fine-grained planet–telluric ΔRV grid.  The window and step are named
    # here and reused in every label, so the text cannot drift from the values
    # actually used.
    win_txt = (f"T$_1$−{drv_pad_min:.0f} min → "
               f"T$_4$+{drv_pad_min:.0f} min")
    geom = event.get("_geom") or {}
    t14_h = geom.get("t14_h")
    drv_info = compute_planet_telluric_drv(
        event, obs, target, vsys_kms, kp_kms, t14_h,
        pad_min=drv_pad_min, step_s=drv_step_s,
    )

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(16, 6),
        gridspec_kw=dict(width_ratios=[3, 2.2]),
    )
    ax.plot(rv, ccor_earth, color=C_TELLURIC, linestyle="-", lw=1.6,
            label="Telluric (Earth frame)")
    ax.plot(rv_star, ccor_earth, color=C_STAR, linestyle=":", lw=2.0,
            label=f"Star ($v_\\star$ = {vtot:+.2f} km/s)")

    # Guides, deliberately unlabelled and neutral: the telluric rest frame at
    # 0 and the stellar velocity, both already implied by the curves above.
    ax.axvline(0.0, color=C_GUIDE, lw=0.6, ls=":", alpha=0.8)
    ax.axvline(vtot, color=C_GUIDE, lw=0.6, ls=":", alpha=0.8)

    # Planet RV band in the Earth/telluric frame, over the same ΔRV grid as
    # the right subplot so the two panels are directly comparable.  Falls back
    # to the synthetic-exposure grid when the geometry needed by
    # `compute_planet_telluric_drv` is missing.
    kp_band = None
    if drv_info is not None:
        rv_p_min, rv_p_max = drv_info["min"], drv_info["max"]
        # Named symmetrically with the circular band below: each says which
        # orbital solution it represents rather than leaving it to inference.
        # The very same string labels the corresponding trace on the right
        # panel, so one quantity keeps one name across the figure; the time
        # window it covers is stated once, in the right panel's title.
        band_label = _solution_label(drv_info)
        ax.axvspan(rv_p_min, rv_p_max, color=C_PLANET, alpha=0.18,
                   zorder=1, label=band_label)
        if rv_p_max - rv_p_min < 0.5:  # nearly a line
            ax.axvline(0.5 * (rv_p_min + rv_p_max), color=C_PLANET,
                       lw=1.0, alpha=0.8)
        kp_band = (rv_p_min, rv_p_max)

        # For an eccentric orbit, outline what the circular approximation
        # would have predicted, so the two can be compared without leaving
        # the page.
        if drv_info["mode"] != "circular":
            circ_min = float(np.min(drv_info["drv_circ"]))
            circ_max = float(np.max(drv_info["drv_circ"]))
            ax.axvspan(circ_min, circ_max, facecolor=C_CIRCULAR, alpha=0.10,
                       edgecolor=C_CIRCULAR, lw=1.0, ls="--", zorder=2,
                       label="Planet RV, circular approx.")
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
        ax.axvspan(rv_p_min, rv_p_max, color=C_PLANET, alpha=0.18,
                   zorder=1,
                   label="Planet RV, circular  [observing window]")
        if rv_p_max - rv_p_min < 0.5:
            ax.axvline(0.5 * (rv_p_min + rv_p_max), color=C_PLANET,
                       lw=1.0, alpha=0.8)
        kp_band = (rv_p_min, rv_p_max)

    # X range: the CC grid plus everything else drawn on the panel.  The grid
    # alone used to clip the star and the circular-approximation band whenever
    # they fell outside +-50 km/s, which is exactly when the comparison
    # matters most.  The CC curves simply end where the grid ends.
    x_of_interest = [rv.min(), rv.max(), rv_star.min(), rv_star.max(), 0.0]
    if kp_band is not None:
        x_of_interest.extend(kp_band)
    if drv_info is not None and drv_info["mode"] != "circular":
        x_of_interest.append(float(np.min(drv_info["drv_circ"])))
        x_of_interest.append(float(np.max(drv_info["drv_circ"])))
    x_lo, x_hi = min(x_of_interest), max(x_of_interest)
    pad = 0.04 * (x_hi - x_lo) or 1.0
    ax.set_xlim(x_lo - pad, x_hi + pad)
    ax.set_ylim(0.95, 1.03)
    ax.set_xlabel("RV [km/s]  (Earth frame, tellurics at 0)")
    ax.set_ylabel("Normalized cross-correlation")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=10)

    ax.set_title(
        f"Telluric position: {name}  |  "
        f"{event_type.replace('_', ' ').title()}  |  {date_str}",
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
        # Envelope over all omega, drawn first so the traces sit on top.
        if drv_info["drv_lo"] is not None:
            ax2.fill_betweenx(
                phase_plot, drv_info["drv_lo"], drv_info["drv_hi"],
                color=C_PLANET, alpha=0.16, zorder=1,
                label=_solution_label(drv_info),
            )
        # In envelope mode the drawn line IS the circular solution, so it takes
        # the circular colour and name: the same quantity keeps one identity
        # across both panels.  Under a Keplerian solution the two are genuinely
        # distinct curves and both are drawn.
        is_envelope = drv_info["mode"] == "envelope"
        if drv_info["mode"] == "keplerian":
            ax2.plot(drv_info["drv_circ"], phase_plot, color=C_CIRCULAR,
                     lw=1.2, ls="--", zorder=2,
                     label="Planet RV, circular approx.")
        trace_colour = C_CIRCULAR if is_envelope else C_PLANET
        trace_label = ("Planet RV, circular approx." if is_envelope
                       else _solution_label(drv_info))
        ax2.plot(drv, phase_plot, color=trace_colour, lw=1.4,
                 ls="--" if is_envelope else "-",
                 marker="o", ms=2.6, mfc=trace_colour, mec="none", zorder=3,
                 label=trace_label)
        ax2.axhspan(phi_t1, phi_t4, color=C_T14, alpha=0.28, zorder=0,
                    label=r"$T_{14}$ (transit duration)")
        # Neutral guides: mid-transit and the telluric rest frame.
        ax2.axhline(0.0, color=C_GUIDE, lw=0.6, ls=":", alpha=0.8)
        ax2.axvline(0.0, color=C_GUIDE, lw=0.6, ls=":", alpha=0.8)
        ax2.set_xlabel(r"$\Delta$RV planet − telluric [km/s]"
                       "\n(Earth frame, tellurics at 0)")
        ax2.set_ylabel(r"Phase relative to transit ($\varphi$ = 0 at mid-transit)")
        ax2.set_title(
            r"$\langle\Delta$RV$\rangle$ = "
            f"{drv_info['mean']:+.2f} km/s,  "
            f"{'possible range' if is_envelope else 'range'} "
            f"[{drv_info['min']:+.2f}, {drv_info['max']:+.2f}] km/s\n"
            f"{win_txt}, {drv_step_s:.0f} s step",
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
            f"$K_p$ = {float(kp_kms):.2f} km/s; planet RV $\\in$ "
            f"[{kp_band[0]:+.2f}, {kp_band[1]:+.2f}] km/s"
        )
    elif kp_kms is None or not np.isfinite(kp_kms):
        kp_line = "$K_p$: not available"
    else:
        kp_line = ""

    # Orbit treatment: what was assumed, and how far the circular
    # approximation would have been off for this target.
    orbit_line = ""
    if drv_info is not None and drv_info["mode"] != "circular":
        omega_txt = (f"$\\omega_p$ = {drv_info['omega_used']:.1f}$^\\circ$"
                     if drv_info["omega_used"] is not None
                     else r"$\omega_p$ unknown, envelope over [0,360)$^\circ$")
        orbit_line = SEP.join([
            f"orbit: e = {drv_info['ecc']:.3f}, {omega_txt}",
            f"$K_p$ = {drv_info['kp_circ']:.2f} (circ.) $\\rightarrow$ "
            f"{drv_info['kp_ecc']:.2f} km/s",
            f"max |$\\Delta$RV$_{{\\rm ecc}}$ − $\\Delta$RV$_{{\\rm circ}}$| "
            f"= {drv_info['max_dev_circ']:.2f} km/s",
        ])

    if drv_info is not None:
        drv_line = (
            r"$\langle\Delta$RV$\rangle$"
            f" = {drv_info['mean']:+.2f} km/s; "
            f"range [{drv_info['min']:+.2f}, {drv_info['max']:+.2f}], "
            f"span {drv_info['span']:.2f} km/s "
            f"({win_txt}, {drv_step_s:.0f} s step)"
        )
    else:
        drv_line = ""

    # The info block sits below the panels, in wide lines rather than a tall
    # stack: inside the axes it grew to cover the cross-correlation curves it
    # was meant to annotate.
    lines = [SEP.join([
        f"$v_{{\\rm sys}}$ = {vsys_kms:+.3f}",
        f"$\\langle v_{{\\rm bary}}\\rangle$ = {vbary_mean:+.3f}",
        f"$v_\\star$ = {vtot:+.3f} km/s (star in Earth frame)",
        f"$n_{{\\rm exp}}$ = {n_exp} ({exp_time_s:.0f}s cadence, "
        f"span {span_h:.2f} h)",
        f"BJD$_{{\\rm TDB}}$ {bjd_start:.5f} → {bjd_end:.5f}",
    ])]
    if kp_line or drv_line:
        lines.append(SEP.join([s for s in (kp_line, drv_line) if s]))
    if orbit_line:
        lines.append(orbit_line)

    fig.text(
        0.005, 0.005, "\n".join(lines),
        ha="left", va="bottom", fontsize=8.5, family="monospace",
        bbox=dict(boxstyle="round,pad=0.5",
                  facecolor="white", edgecolor="#bbbbbb", alpha=0.9),
    )

    # Leave room at the bottom for the info block.
    fig.tight_layout(rect=(0.0, 0.02 + 0.045 * len(lines), 1.0, 1.0))
    pdf.savefig(fig, dpi=150, bbox_inches="tight")
    # Released from pyplot's registry so a long run does not accumulate
    # figures; the returned object stays inspectable for the tests.
    plt.close(fig)
    return fig
