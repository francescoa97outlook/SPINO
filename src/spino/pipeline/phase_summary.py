"""
Phase Scheduler - Per-planet Summary Card
==========================================
Renders a one-page A4 PDF with stellar / planetary / orbital /
spectroscopy parameters for a single planet.

When magnitudes (J, H, K, V) or other inputs needed by the TSM/ESM
calculation (Kempton et al. 2018) are missing in the NEA row, this
module queries Simbad as a best-effort fallback.  Fields that remain
unknown after that are rendered as ``/`` rather than dropping the
planet from the report.
"""
from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from astroquery.simbad import Simbad

from phase_tsm_calculator import TSM_ESM_Calculator
from phase_scale_height import compute_scale_height


_MISSING = "/"
_BANDS = ("J", "H", "K", "V")
_simbad_mag_cache: dict[str, dict[str, float]] = {}


# ============================================================== #
#  SIMBAD FALLBACK                                                #
# ============================================================== #
def fetch_simbad_mags(star_name: str) -> dict[str, float]:
    """
    Query Simbad for J/H/K/V magnitudes of *star_name*.  Missing
    bands → np.nan.  Errors → all bands np.nan.  Cached by name.
    """
    out = {b: np.nan for b in _BANDS}
    if not star_name or pd.isna(star_name):
        return out
    if star_name in _simbad_mag_cache:
        return _simbad_mag_cache[star_name]

    try:
        s = Simbad()
        s.add_votable_fields(*_BANDS)
        tab = s.query_object(star_name)
        if tab is not None and len(tab) > 0:
            for band in _BANDS:
                for col in (band, f"FLUX_{band}"):
                    if col in tab.colnames and not np.ma.is_masked(tab[col][0]):
                        out[band] = float(tab[col][0])
                        break
    except Exception as e:
        print(f"      × Simbad mag error for {star_name!r}: {e}")

    _simbad_mag_cache[star_name] = out
    return out


def _resolve_mags(row) -> dict[str, float]:
    """Read NEA mags from *row*; fill missing bands from Simbad."""
    mags = {
        "J": row.get("sy_jmag", np.nan),
        "H": row.get("sy_hmag", np.nan),
        "K": row.get("sy_kmag", np.nan),
        "V": row.get("sy_vmag", np.nan),
    }
    if any(pd.isna(v) for v in mags.values()):
        host = str(row.get("hostname") or row.get("pl_name") or "").strip()
        sim = fetch_simbad_mags(host)
        for band, val in sim.items():
            if pd.isna(mags[band]) and pd.notna(val):
                mags[band] = val
    return mags


# ============================================================== #
#  TSM / ESM + SCALE HEIGHT                                       #
# ============================================================== #
def _finite(x) -> bool:
    try:
        return pd.notna(x) and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def compute_tsm_esm(row, mags: dict[str, float]) -> dict | None:
    """Run TSM_ESM_Calculator; return its dict, or None if inputs missing."""
    rp = row.get("pl_rade")
    rs = row.get("st_rad")
    teff = row.get("st_teff")
    teq = row.get("pl_eqt")
    a_au = row.get("pl_orbsmax")
    mp = row.get("pl_bmasse")
    mj, mk = mags.get("J"), mags.get("K")

    if not all(_finite(x) for x in (rp, rs, teff, mj, mk)):
        return None
    if not (_finite(teq) or _finite(a_au)):
        return None

    payload: dict = {
        "name": str(row.get("pl_name", "?")),
        "Rp_Rearth": float(rp),
        "Rs_Rsun": float(rs),
        "Teff_star": float(teff),
        "mag_J": float(mj),
        "mag_K": float(mk),
    }
    if _finite(teq):
        payload["Teq"] = float(teq)
    if _finite(a_au):
        payload["a_AU"] = float(a_au)
    if _finite(mp):
        payload["Mp_Mearth"] = float(mp)

    try:
        return TSM_ESM_Calculator().compute(payload)
    except Exception as e:
        print(f"      × TSM/ESM compute error: {e}")
        return None


def compute_kp(row, tsm_row=None) -> float | None:
    """
    Planetary RV semi-amplitude K_p [km/s] from NEA row.
    Falls back to ``tsm_row['Mp_Mearth']`` (Chen-Kipping estimate) when
    ``pl_bmasse`` is missing, and to i = 90° when ``pl_orbincl`` is missing.
    Returns None if period or stellar mass are unavailable.
    """
    period = row.get("pl_orbper")
    ms_sun = row.get("st_mass")
    mp_earth = row.get("pl_bmasse")
    if not _finite(mp_earth) and tsm_row:
        mp_earth = tsm_row.get("Mp_Mearth")
    incl = row.get("pl_orbincl")
    if not all(_finite(x) for x in (period, ms_sun, mp_earth)):
        return None

    sin_i = np.sin(np.deg2rad(float(incl))) if _finite(incl) else 1.0
    # SI physical constants (inlined to avoid a heavy petitRADTRANS dependency;
    # these match petitRADTRANS.physical_constants converted from cgs to SI).
    M_earth = 5.9722e24   # kg
    M_sun = 1.98892e30    # kg
    G_si = 6.67430e-11    # m^3 kg^-1 s^-2
    P_s = float(period) * 86400.0
    Mp = float(mp_earth) * M_earth
    Ms = float(ms_sun) * M_sun
    Mp_min = Mp * sin_i
    if Mp_min <= 0:
        return None

    # Stellar RV semi-amplitude [m/s]
    Ks = ((2 * np.pi * G_si) ** (1 / 3) * Mp_min) / (
        P_s ** (1 / 3) * (Ms + Mp_min) ** (2 / 3)
    )
    Kp = Ms * Ks / Mp_min  # m/s
    return Kp / 1e3  # km/s


def compute_scale_heights(row, tsm_row) -> dict | None:
    """Compute scale heights for 4 fiducial μ scenarios."""
    if not tsm_row:
        return None
    rp = tsm_row.get("Rp_Rearth", row.get("pl_rade"))
    mp = tsm_row.get("Mp_Mearth", row.get("pl_bmasse"))
    teq = tsm_row.get("Teq_K", row.get("pl_eqt"))
    if not all(_finite(x) and float(x) > 0 for x in (rp, mp, teq)):
        return None

    scenarios = (
        ("Light (μ=2.3)",  2.3),
        ("Medium (μ=3.0)", 3.0),
        ("Heavy (μ=4.0)",  4.0),
        ("Dense (μ=6.0)",  6.0),
    )
    out = {}
    for name, mu in scenarios:
        try:
            out[name] = compute_scale_height(
                M_planet=float(mp), R_planet=float(rp), T_eq=float(teq),
                mu=mu, M_unit="Mearth", R_unit="Rearth",
            )
        except Exception:
            pass
    return out or None


# ============================================================== #
#  PDF RENDERING                                                  #
# ============================================================== #
def _safe_name(name) -> str:
    return re.sub(r"[^\w\-]", "_", str(name)).strip("_")


def _fmt(val, fmt: str = ".3f") -> str:
    """Format *val* numerically; return '/' on NaN / None / non-numeric."""
    if val is None:
        return _MISSING
    try:
        if pd.isna(val):
            return _MISSING
    except (TypeError, ValueError):
        pass
    try:
        return format(float(val), fmt)
    except (TypeError, ValueError):
        s = str(val).strip()
        return s if s and s.lower() != "nan" else _MISSING


def _short_ref(refname) -> str:
    """
    Extract a short "Author+Year" citation from NEA pl_refname HTML.
    Examples:
      "<a refstr=KOKORI_ET_AL__2023 ...>Kokori et al. 2023</a>" → "Kokori+2023"
      "Bonomo et al. 2017"                                     → "Bonomo+2017"
      ""                                                        → ""
    Falls back to the input string trimmed/truncated when parsing fails.
    """
    if refname is None:
        return ""
    try:
        if pd.isna(refname):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(refname).strip()
    if not s:
        return ""

    m = re.search(r"refstr=([A-Z][A-Z0-9_]*?)(?:_+ET_AL)?(?:__|_)(\d{4})",
                  s, re.IGNORECASE)
    if m:
        author = m.group(1).split("_")[0].capitalize()
        return f"{author}+{m.group(2)}"

    text_m = re.search(r">([^<]+)<", s)
    visible = (text_m.group(1) if text_m else s).strip()
    year_m = re.search(r"(\d{4})", visible)
    name_m = re.match(r"\s*([A-Za-z]+)", visible)
    if name_m and year_m:
        return f"{name_m.group(1)}+{year_m.group(1)}"
    return visible[:24]


def save_planet_summary(row, tsm_row, sh_results, planet_dir,
                        mags=None, geom=None) -> str:
    """
    Render the per-planet summary PDF in *planet_dir*.  Returns the path.
    Missing values render as ``/``; never raises on missing data.
    """
    name = str(row.get("pl_name", "Unknown"))
    safe = _safe_name(name)
    ra = row.get("ra")
    dec = row.get("dec")

    fig = plt.figure(figsize=(8.27, 11.69))   # A4 portrait
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── Header bar ───────────────────────────────────────────────────
    ax.add_patch(plt.Rectangle((0.04, 0.910), 0.92, 0.078,
                               color="#1F3440", clip_on=False))
    ax.text(0.07, 0.952, name, fontsize=18, fontweight="bold",
            color="white", fontfamily="serif", va="center")

    ref_raw = str(row.get("pl_refname", "") or "")
    if ref_raw:
        from html import unescape
        url_m = re.search(r"href=([^\s>]+)", ref_raw)
        text_m = re.search(r">([^<]+)<", ref_raw)
        ref_url = url_m.group(1) if url_m else ""
        ref_disp = unescape(text_m.group(1)) if text_m else ref_raw
        kw = dict(url=ref_url) if ref_url else {}
        ax.text(0.07, 0.920, ref_disp[:110],
                fontsize=7.5, color="#7fb3cc", fontfamily="serif",
                va="center", style="italic", **kw)

    try:
        coord_str = (f"RA {float(ra):.4f}°  Dec {float(dec):+.4f}°"
                     if pd.notna(ra) and pd.notna(dec) else "")
    except (TypeError, ValueError):
        coord_str = ""
    ax.text(0.93, 0.949, coord_str, fontsize=9.5, color="#cccccc",
            fontfamily="serif", va="center", ha="right")

    src = row.get("catalog_source")
    src_str = f"Source: {src}" if pd.notna(src) and str(src) else f"Source: {_MISSING}"
    ax.text(0.93, 0.928, src_str, fontsize=9.0, color="#cccccc",
            fontfamily="serif", va="center", ha="right", style="italic")

    field_sources = row.get("_field_sources") or {}
    if not isinstance(field_sources, dict):
        field_sources = {}

    def src_of(field):
        return _short_ref(field_sources.get(field, ""))

    eph_ref = src_of("pl_orbper") or src_of("pl_tranmid")
    if eph_ref:
        ax.text(0.93, 0.908, f"Ephemeris: {eph_ref} (P, T₀)",
                fontsize=8.5, color="#aabbcc",
                fontfamily="serif", va="center", ha="right", style="italic")

    dy = 0.032

    def sec(x, y, text):
        ax.text(x, y, text, fontsize=11, fontweight="bold",
                color="#1F3440", fontfamily="serif", va="top")
        ax.plot([x, x + 0.43], [y - 0.013, y - 0.013],
                color="#1F3440", lw=1.2)

    def prow(x, y, label, val, unit="", src=""):
        ax.text(x, y, label, fontsize=10, color="#555",
                fontfamily="serif", va="top")
        ax.text(x + 0.185, y, f"{val}  {unit}".strip(),
                fontsize=10, color="#111", fontfamily="serif",
                fontweight="bold", va="top")
        if src:
            ax.text(x + 0.42, y, f"[{src}]", fontsize=7,
                    color="#888888", fontfamily="serif",
                    va="top", ha="right", style="italic")

    if mags is None:
        mags = _resolve_mags(row)

    # ── LEFT COLUMN: Stellar + Orbital ───────────────────────────────
    xl, yl = 0.06, 0.885
    sec(xl, yl, "Stellar")
    star_name = str(row.get("hostname", "") or "").strip() or _MISSING
    sp_type = str(row.get("st_spectype", "") or "").strip() or _MISSING
    stellar = [
        ("Host star",  star_name,                            "",      ""),
        ("Teff",       _fmt(row.get("st_teff"),  ".0f"),     "K",     src_of("st_teff")),
        (r"$R_\star$", _fmt(row.get("st_rad"),   ".3f"),     "$R_S$", src_of("st_rad")),
        (r"$M_\star$", _fmt(row.get("st_mass"),  ".3f"),     "$M_S$", src_of("st_mass")),
        ("[Fe/H]",     _fmt(row.get("st_met"),   "+.2f"),    "",      src_of("st_met")),
        ("J mag",      _fmt(mags.get("J"),       ".2f"),     "",      src_of("sy_jmag")),
        ("H mag",      _fmt(mags.get("H"),       ".2f"),     "",      src_of("sy_hmag")),
        ("K mag",      _fmt(mags.get("K"),       ".2f"),     "",      src_of("sy_kmag")),
        ("V mag",      _fmt(mags.get("V"),       ".2f"),     "",      src_of("sy_vmag")),
        ("Sp. type",   sp_type,                              "",      src_of("st_spectype")),
    ]
    last_src = None
    for i, (lbl, val, unit, s) in enumerate(stellar):
        shown = s if s and s != last_src else ""
        prow(xl, yl - dy * (i + 1), lbl, val, unit, src=shown)
        if s:
            last_src = s

    yl_orb = yl - dy * (len(stellar) + 2.0)
    sec(xl, yl_orb, "Orbital")
    if geom is not None:
        t14, t23 = geom.get("t14_h"), geom.get("t23_h")
        t12 = geom.get("t12_h")
        if t12 is None and t14 is not None and t23 is not None:
            try:
                t12 = (float(t14) - float(t23)) / 2.0
            except (TypeError, ValueError):
                t12 = np.nan
        phi_s = geom.get("phi_sec")
        t14_sec = geom.get("t14_sec_h")
    else:
        t14 = t23 = t12 = phi_s = t14_sec = np.nan

    kp_kms = compute_kp(row, tsm_row)

    orbital = [
        ("Period",        _fmt(row.get("pl_orbper"),   ".6f"), "d",     src_of("pl_orbper")),
        ("T₀ (BJD)",      _fmt(row.get("pl_tranmid"),  ".4f"), "",      src_of("pl_tranmid")),
        ("a",             _fmt(row.get("pl_orbsmax"),  ".4f"), "AU",    src_of("pl_orbsmax")),
        ("e",             _fmt(row.get("pl_orbeccen"), ".4f"), "",      src_of("pl_orbeccen")),
        ("ω",             _fmt(row.get("pl_orblper"),  ".2f"), "°",     src_of("pl_orblper")),
        ("i",             _fmt(row.get("pl_orbincl"),  ".2f"), "°",     src_of("pl_orbincl")),
        ("Kp",            _fmt(kp_kms,                 ".3f"), "km s⁻¹", ""),
        ("T₁₄ (prim.)",   _fmt(t14,                    ".3f"), "h",     ""),
        ("T₂₃ (prim.)",   _fmt(t23,                    ".3f"), "h",     ""),
        ("T₁₂ ingress",   _fmt(t12,                    ".3f"), "h",     ""),
        ("φ_sec",         _fmt(phi_s,                  ".5f"), "",      ""),
        ("T₁₄ (sec.)",    _fmt(t14_sec,                ".3f"), "h",     ""),
    ]
    last_src = None
    for i, (lbl, val, unit, s) in enumerate(orbital):
        shown = s if s and s != last_src else ""
        prow(xl, yl_orb - dy * (i + 1), lbl, val, unit, src=shown)
        if s:
            last_src = s

    # ── RIGHT COLUMN: Planetary + Spectroscopy + Atmosphere ─────────
    xr, yr = 0.52, 0.885
    sec(xr, yr, "Planetary")
    rp = (tsm_row or {}).get("Rp_Rearth", row.get("pl_rade"))
    mp = (tsm_row or {}).get("Mp_Mearth", row.get("pl_bmasse"))
    rho = (tsm_row or {}).get("density_gcm3")
    teq = (tsm_row or {}).get("Teq_K", row.get("pl_eqt"))
    cat = (tsm_row or {}).get("category") or _MISSING
    mass_est = bool((tsm_row or {}).get("mass_estimated", False))
    mp_str = f"{_fmt(mp, '.2f')}{'*' if mass_est else ''}"

    planetary = [
        ("Rp",       _fmt(rp,  ".3f"), "R⊕",     src_of("pl_rade")),
        ("Mp",       mp_str,           "M⊕",     src_of("pl_bmasse")),
        ("ρ",        _fmt(rho, ".2f"), "g cm⁻³", ""),
        ("Teq",      _fmt(teq, ".0f"), "K",      src_of("pl_eqt")),
        ("Category", str(cat),         "",       ""),
    ]
    last_src = None
    for i, (lbl, val, unit, s) in enumerate(planetary):
        shown = s if s and s != last_src else ""
        prow(xr, yr - dy * (i + 1), lbl, val, unit, src=shown)
        if s:
            last_src = s

    if mass_est:
        ax.text(xr, yr - dy * (len(planetary) + 1.5),
                "* Chen & Kipping (2017) mass estimate",
                fontsize=7.5, color="#999", fontfamily="serif",
                va="top", style="italic")

    yr_spec = yr - dy * (len(planetary) + 2.8 + (0.9 if mass_est else 0))
    sec(xr, yr_spec, "Spectroscopy  (Kempton et al. 2018)")

    if tsm_row:
        tsm_val = float(tsm_row.get("TSM", np.nan))
        esm_val = float(tsm_row.get("ESM", np.nan))
        tsm_thr = float(tsm_row.get("TSM_threshold", 90) or 90)
        esm_thr = float(tsm_row.get("ESM_threshold", 7.5) or 7.5)
        tsm_ok = bool(tsm_row.get("TSM_above", False))
        esm_ok = bool(tsm_row.get("ESM_above", False))
    else:
        tsm_val = esm_val = np.nan
        tsm_thr, esm_thr = 90.0, 7.5
        tsm_ok = esm_ok = False

    for k, (metric, val, thr, ok) in enumerate([
        ("TSM", tsm_val, tsm_thr, tsm_ok),
        ("ESM", esm_val, esm_thr, esm_ok),
    ]):
        y_line = yr_spec - dy * (k + 1)
        if _finite(val):
            tick_char = "✓" if ok else "✗"
            tick_col = "#1a7a1a" if ok else "#aa1111"
            value_str = f"{_fmt(val, '.1f')}  (thr {thr:g})"
        else:
            tick_char = ""
            tick_col = "#666666"
            value_str = f"{_MISSING}  (thr {thr:g})"
        ax.text(xr, y_line, metric, fontsize=10, color="#555",
                fontfamily="serif", va="top")
        ax.text(xr + 0.09, y_line, value_str, fontsize=10, color="#111",
                fontfamily="serif", fontweight="bold", va="top")
        ax.text(xr + 0.40, y_line, tick_char, fontsize=13, color=tick_col,
                va="top", fontweight="bold")

    if sh_results:
        yr_atm = yr_spec - dy * 4.2
        sec(xr, yr_atm, "Atmosphere  (Scale Height)")
        first = next(iter(sh_results.values()))
        prow(xr, yr_atm - dy, "g", f"{first['g']:.2f}", "m s⁻²")

        y_hdr = yr_atm - dy * 1.85
        ax.text(xr + 0.01, y_hdr, "Scenario", fontsize=8, color="#888",
                fontfamily="serif", va="top", style="italic")
        ax.text(xr + 0.22, y_hdr, "H [km]", fontsize=8, color="#888",
                fontfamily="serif", va="top")
        ax.text(xr + 0.32, y_hdr, "μ [g/mol]", fontsize=8, color="#888",
                fontfamily="serif", va="top")
        for i, (cfg_name, sh) in enumerate(sh_results.items()):
            y_row = yr_atm - dy * (2.5 + i)
            ax.text(xr + 0.01, y_row, cfg_name, fontsize=8.5, color="#333",
                    fontfamily="serif", va="top", style="italic")
            ax.text(xr + 0.22, y_row, f"{sh['H_km']:.1f}",
                    fontsize=8.5, color="#111", fontfamily="serif",
                    fontweight="bold", va="top")
            ax.text(xr + 0.32, y_row, f"{sh['mu']:.3f}",
                    fontsize=8.5, color="#111", fontfamily="serif",
                    fontweight="bold", va="top")
        ax.text(xr + 0.01, yr_atm - dy * (2.5 + len(sh_results) + 0.6),
                f"T = T_eq = {first['T_eq']:.0f} K",
                fontsize=7.5, color="#999", fontfamily="serif",
                va="top", style="italic")

    # ── Bottom bar charts ────────────────────────────────────────────
    for k, (val, thr, label, cmap_name) in enumerate([
        (tsm_val, tsm_thr, "TSM", "plasma"),
        (esm_val, esm_thr, "ESM", "cividis"),
    ]):
        bax = fig.add_axes([0.10, 0.060 - k * 0.042, 0.80, 0.028])
        bax.axis("off")
        bar_max = max(
            val * 1.25 if _finite(val) and val > 0 else thr * 2,
            thr * 1.6,
        )
        bax.set_xlim(0, bar_max)
        bax.set_ylim(0, 1)
        bax.barh(0.5, bar_max, height=0.80, color="#eeeeee", zorder=1)
        if _finite(val) and val > 0:
            cmap = plt.get_cmap(cmap_name)
            bax.barh(0.5, val, height=0.80, color=cmap(0.65),
                     zorder=2, alpha=0.85)
        bax.axvline(thr, color="#222", lw=1.5, ls="--", zorder=3)
        bax.text(-0.01, 0.5, label, transform=bax.transAxes, fontsize=9,
                 fontfamily="serif", color="#333", va="center", ha="right")
        if _finite(val) and val > 0:
            x_txt = min(val + bar_max * 0.015, bar_max * 0.97)
            bax.text(x_txt, 0.5, f"{val:.1f}", fontsize=8,
                     fontfamily="serif", color="#111",
                     va="center", ha="left")
        else:
            bax.text(bar_max * 0.5, 0.5, _MISSING, fontsize=10,
                     fontfamily="serif", color="#888",
                     va="center", ha="center")
        bax.text(thr + bar_max * 0.015, 0.05,
                 f"threshold {thr:g}", fontsize=7,
                 fontfamily="serif", color="#666", va="bottom")

    ax.text(0.50, 0.005,
            "Neptunian Desert - Planet Parameter Summary",
            fontsize=8, color="#bbbbbb", fontfamily="serif",
            ha="center", va="bottom", style="italic")

    out = os.path.join(planet_dir, f"{safe}_summary.pdf")
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ============================================================== #
#  PUBLIC ENTRY POINTS                                            #
# ============================================================== #
def compute_planet_metrics(row) -> dict:
    """
    Resolve mags (Simbad fallback) and compute TSM/ESM and scale
    heights when possible.  Returns a dict::

        {
            "mags":    {"J": ..., "H": ..., "K": ..., "V": ...},
            "tsm_row": <TSM_ESM_Calculator output dict or None>,
            "sh":      <scale-height dict or None>,
        }

    ``tsm_row`` is None when essential inputs are missing (Rp, Rs,
    Teff, J, K, plus Teq or a_AU).  Callers can read
    ``tsm_row["TSM_above"]`` / ``["ESM_above"]`` to check thresholds.
    """
    mags = _resolve_mags(row)
    tsm_row = compute_tsm_esm(row, mags)
    sh = compute_scale_heights(row, tsm_row) if tsm_row else None
    return {"mags": mags, "tsm_row": tsm_row, "sh": sh}


def render_planet_summary(row, metrics: dict, planet_dir: str,
                          geom=None) -> str:
    """
    Render the per-planet summary PDF using precomputed *metrics*
    (from ``compute_planet_metrics``).  Returns the output path.
    """
    os.makedirs(planet_dir, exist_ok=True)
    return save_planet_summary(
        row,
        metrics.get("tsm_row"),
        metrics.get("sh"),
        planet_dir,
        mags=metrics.get("mags"),
        geom=geom,
    )


def build_planet_summary(row, planet_dir: str, geom=None) -> str:
    """
    Convenience wrapper: compute metrics + render in one call.
    Use ``compute_planet_metrics`` + ``render_planet_summary`` directly
    when callers need access to TSM/ESM before creating the directory.
    """
    metrics = compute_planet_metrics(row)
    return render_planet_summary(row, metrics, planet_dir, geom=geom)
