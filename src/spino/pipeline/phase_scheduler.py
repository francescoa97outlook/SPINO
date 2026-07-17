"""
Phase Scheduler
===============
Standalone tool to schedule transit, pre-eclipse, and post-eclipse
observations.  Reads the NASA Exoplanet Archive PS table, filters by
user criteria, computes observable events per night, and produces
altitude-vs-time plots, calendar summaries, and a P-R desert landscape.

All configuration lives in phase_config.py.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath

from astropy.coordinates import (
    SkyCoord, EarthLocation, AltAz, get_body, get_sun,
)
from astropy.coordinates.baseframe import NonRotationTransformationWarning
from astropy.time import Time
from astropy.utils.exceptions import AstropyWarning
import astropy.units as u

# Moon/target separations are computed across ICRS↔GCRS; astropy ≥6 warns
# that the result depends on the direction of the transformation.  For our
# use case (degree-level Moon distance and illumination) the difference is
# sub-arcsecond, so silence the warning rather than flooding the console.
warnings.filterwarnings("ignore", category=NonRotationTransformationWarning)

# Scheduling looks at *future* observation dates that lie beyond the IERS
# Earth-orientation data bundled with astropy, so astropy falls back to the
# 50-yr mean polar motion and warns.  The resulting error is at the arcsec
# level - negligible for visibility/airmass - so silence just this message
# (matched by text, to avoid muting unrelated AstropyWarnings).
warnings.filterwarnings(
    "ignore",
    message=r".*polar motion.*",
    category=AstropyWarning,
)

from phase_config import CUSTOM_PLANETS

# ================================================================== #
#  CONSTANTS                                                          #
# ================================================================== #
_R_SUN_AU = 0.00465047                    # R_Sun in AU
_R_EARTH_RSUN = 6.371e6 / 6.957e8        # R_Earth / R_Sun
RJUP_TO_REARTH = 11.209                   # R_Jup / R_Earth


# ================================================================== #
#  1. CATALOG LOADING                                                 #
# ================================================================== #
def load_catalog(csv_path, source):
    """
    Load a NASA Exoplanet Archive PS CSV.
    Keep only confirmed, non-controversial planets.

    ``source`` is one of "NEA", "TESS", "BOTH" and controls the
    derived ``catalog_source`` column:
      - "NEA"  → all rows get "NEA"
      - "TESS" → all rows get "TESS"
      - "BOTH" → per row: "TESS" if disc_facility contains "TESS",
                          else "NEA"
    """
    if source not in ("NEA", "TESS", "BOTH"):
        raise ValueError(
            f"source must be one of NEA/TESS/BOTH, got {source!r}"
        )

    df = pd.read_csv(csv_path, comment="#")

    for col in ("pl_orbper", "pl_rade", "pl_bmasse", "pl_tranmid",
                "ra", "dec", "pl_eqt"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "soltype" in df.columns:
        df = df[df["soltype"] == "Published Confirmed"]
    if "pl_controv_flag" in df.columns:
        df = df[df["pl_controv_flag"] == 0]

    if "pl_pubdate" in df.columns:
        df["pl_pubdate"] = pd.to_datetime(df["pl_pubdate"], errors="coerce")
        df = df.sort_values("pl_pubdate", ascending=False)

    # Keep ephemeris-only rows (e.g. Kokori, Ivshina) that lack pl_rade -
    # compose_best_rows will pull the radius from a different reference.
    df = df.dropna(subset=["pl_orbper"])
    df = df[df["pl_orbper"] > 0]

    if source == "BOTH":
        # Prefer disc_facility (matches the NEA TAP URL convention); fall
        # back to disc_telescope so this also works on cached CSVs that
        # were downloaded before disc_facility was added to NEA_COLUMNS.
        if "disc_facility" in df.columns:
            disc = df["disc_facility"]
        elif "disc_telescope" in df.columns:
            disc = df["disc_telescope"]
        else:
            disc = pd.Series([""] * len(df), index=df.index)
        df["catalog_source"] = np.where(
            disc.fillna("").str.contains("TESS", case=False, na=False),
            "TESS", "NEA",
        )
    else:
        df["catalog_source"] = source

    return df.reset_index(drop=True)


# ================================================================== #
#  2. DESERT POLYGON                                                  #
# ================================================================== #
def load_desert_polygon(boundary_file):
    """Load the CG24 KDE boundary as a closed matplotlib Path."""
    data = np.loadtxt(boundary_file, skiprows=1)
    bx, by = data[:, 0], data[:, 1]
    if not (np.isclose(bx[0], bx[-1]) and np.isclose(by[0], by[-1])):
        bx = np.append(bx, bx[0])
        by = np.append(by, by[0])
    return MplPath(np.column_stack([bx, by]))


def is_in_desert(period, radius_earth, polygon):
    """True if planet is in the desert (outside KDE contour, inside bbox)."""
    logP = np.log10(np.asarray(period, dtype=float))
    logR = np.log10(np.asarray(radius_earth, dtype=float))
    pts = np.column_stack([logP, logR])
    verts = polygon.vertices
    pmin, pmax = verts[:, 0].min(), verts[:, 0].max()
    rmin, rmax = verts[:, 1].min(), verts[:, 1].max()
    in_bbox = ((logP >= pmin) & (logP <= pmax) &
               (logR >= rmin) & (logR <= rmax))
    in_contour = polygon.contains_points(pts)
    return in_bbox & ~in_contour


# ================================================================== #
#  3. CATALOG FILTERING                                               #
# ================================================================== #
def filter_catalog(df, desert_filter, polygon, extra_filters):
    """Apply desert polygon filter + extra column filters."""
    out = df.copy()

    if desert_filter in ("desert", "nondesert") and polygon is not None:
        mask = is_in_desert(out["pl_orbper"].values,
                            out["pl_rade"].values, polygon)
        if desert_filter == "nondesert":
            mask = ~mask
        removed = out[~mask]
        if not removed.empty:
            print(f"  [desert filter] {len(removed)} removed")
        out = out[mask].reset_index(drop=True)

    for f in extra_filters:
        col = f["column"]
        if col not in out.columns:
            continue
        if "contains" in f:
            m = (out[col].astype(str)
                 .str.contains(f["contains"], case=False, na=False))
        else:
            vals = pd.to_numeric(out[col], errors="coerce")
            m = np.ones(len(out), dtype=bool)
            lo, hi = f.get("min"), f.get("max")
            if lo is not None:
                m &= (vals >= lo)
            if hi is not None:
                m &= (vals <= hi)
        n_removed = (~m).sum()
        if n_removed:
            print(f"  [filter {col}] {n_removed} removed")
        out = out[m].reset_index(drop=True)

    return out


_EPHEMERIS_FIELDS = (
    "pl_orbper", "pl_orbpererr1", "pl_orbpererr2",
    "pl_tranmid", "pl_tranmiderr1", "pl_tranmiderr2",
    "pl_tsystemref",
)
_OTHER_FIELDS = (
    "ra", "dec",
    "pl_orbsmax", "pl_orbsmaxerr1", "pl_orbsmaxerr2",
    "pl_orbeccen", "pl_orblper", "pl_orbincl", "pl_imppar",
    "pl_rade", "pl_radeerr1", "pl_radeerr2",
    "pl_bmasse", "pl_bmasseerr1", "pl_bmasseerr2",
    "pl_masse", "pl_msinie", "pl_dens", "pl_insol",
    "pl_eqt", "pl_trandur", "pl_rvamp",
    "st_teff", "st_rad", "st_mass", "st_met",
    "st_radv", "st_spectype",
    "sy_jmag", "sy_hmag", "sy_kmag", "sy_vmag", "sy_gaiamag",
)
_IDENTITY_FIELDS = (
    "pl_name", "hostname", "catalog_source", "soltype",
    "pl_controv_flag", "default_flag", "discoverymethod",
    "disc_year", "disc_telescope", "disc_facility",
)


def _ephemeris_score(row):
    """Combined relative ephemeris uncertainty: smaller is better."""
    P = row.get("pl_orbper")
    if not pd.notna(P) or P <= 0:
        return np.inf
    e1 = row.get("pl_orbpererr1")
    e2 = row.get("pl_orbpererr2")
    P_errs = [abs(e) for e in (e1, e2) if pd.notna(e)]
    P_err = float(np.mean(P_errs)) if P_errs else np.nan
    t1 = row.get("pl_tranmiderr1")
    t2 = row.get("pl_tranmiderr2")
    T_errs = [abs(e) for e in (t1, t2) if pd.notna(e)]
    T_err = float(np.mean(T_errs)) if T_errs else np.nan
    if pd.isna(P_err) and pd.isna(T_err):
        return np.inf  # no errors → fall through to pubdate tie-break
    P_err = 0.0 if pd.isna(P_err) else P_err
    T_err = 0.0 if pd.isna(T_err) else T_err
    return float(np.sqrt((P_err / P) ** 2 + T_err ** 2))


def compose_best_rows(df):
    """
    Merge multiple references per planet into one composite row.

    Per planet:
      - Ephemeris (pl_orbper, pl_tranmid, errors, pl_tsystemref)
        comes from the row minimizing combined relative ephemeris
        uncertainty (sqrt((sigma_P/P)^2 + sigma_T0^2)); ties broken
        by pl_pubdate desc.  Mimics NEA TransitView's "most precise
        ephemeris" rule.
      - All other fields: per-field, the most recent (pl_pubdate desc)
        non-null value across this planet's rows.
      - Identity fields are inherited from the chosen ephemeris row.

    The returned DataFrame carries an extra column ``_field_sources``
    (dict[field → pl_refname]) so the summary PDF can attribute each
    displayed value to its donor reference.

    Planets with no row containing pl_orbper, pl_tranmid, ra, and dec
    simultaneously are skipped (cannot schedule).
    """
    if df.empty:
        out = df.copy()
        out["_field_sources"] = pd.Series([], dtype=object)
        return out

    if "pl_pubdate" in df.columns:
        df = df.sort_values("pl_pubdate", ascending=False, kind="stable")

    rows_out = []
    skipped = 0
    for name, group in df.groupby("pl_name", sort=False):
        # Ephemeris candidates need the four schedule-essential columns.
        eph_mask = group["pl_orbper"].notna() & group.get(
            "pl_tranmid", pd.Series(False, index=group.index)).notna()
        for col in ("ra", "dec"):
            if col in group.columns:
                eph_mask &= group[col].notna()
            else:
                eph_mask &= False
        eph_candidates = group[eph_mask]
        if eph_candidates.empty:
            skipped += 1
            continue

        scores = eph_candidates.apply(_ephemeris_score, axis=1)
        eph_candidates = eph_candidates.assign(_eph_score=scores).sort_values(
            ["_eph_score", "pl_pubdate"],
            ascending=[True, False],
            kind="stable",
        )
        eph_row = eph_candidates.iloc[0]
        ref_eph = eph_row.get("pl_refname", "")

        composite = {}
        sources = {}

        for f in _IDENTITY_FIELDS:
            if f in eph_row.index:
                composite[f] = eph_row[f]

        for f in _EPHEMERIS_FIELDS:
            if f not in eph_row.index:
                continue
            v = eph_row[f]
            composite[f] = v
            if pd.notna(v) and v != "":
                sources[f] = ref_eph

        for f in _OTHER_FIELDS:
            if f not in group.columns:
                continue
            non_null = group[group[f].notna()]
            if non_null.empty:
                composite[f] = np.nan
                continue
            donor = non_null.iloc[0]   # group is pubdate-desc sorted
            composite[f] = donor[f]
            sources[f] = donor.get("pl_refname", "")

        composite["pl_refname"] = ref_eph
        composite["_field_sources"] = sources
        rows_out.append(composite)

    if skipped:
        print(f"  [compose_best_rows] {skipped} planets skipped "
              "(no row with pl_orbper+pl_tranmid+ra+dec)")

    out = pd.DataFrame(rows_out)
    return out.reset_index(drop=True)


# ================================================================== #
#  3.5  TIME-SCALE NORMALIZATION                                      #
# ================================================================== #
_KNOWN_BJD_TDB    = {"BJDTDB", "BJD"}            # already barycentric-TDB
_KNOWN_HJD        = {"HJD", "HJDUTC"}            # heliocentric (UTC)
_KNOWN_JD_UTC     = {"JD", "JDUTC"}              # geocentric UTC


def _normalize_time_system(systemref):
    """Normalize the pl_tsystemref string to a canonical token."""
    if systemref is None:
        return None
    if isinstance(systemref, float) and pd.isna(systemref):
        return None
    s = str(systemref).strip().upper()
    if not s or s.lower() in ("nan", "none"):
        return None
    return "".join(ch for ch in s if ch.isalnum())


_warned_unknown_tsys = set()


def to_bjd_tdb(t0_value, system_ref, ra_deg, dec_deg):
    """
    Convert ``t0_value`` (Julian Date in the time system named by
    ``system_ref``) to BJD_TDB.  Returns the converted JD as a float.

    Recognized values (NEA convention, matched case-insensitive after
    stripping non-alphanumerics):
      - BJD_TDB / BJD-TDB / BJD : returned unchanged
      - HJD / HJD_UTC           : add (BJD-HJD) using astropy
                                  light_travel_time barycentric/heliocentric
      - JD_UTC / JD             : add (BJD-JD) ≈ (TDB-UTC) + barycentric ltt

    Missing/unknown system refs are treated as BJD_TDB with a one-time
    warning per token, and the value is returned unchanged.
    """
    if not pd.notna(t0_value):
        return t0_value

    tok = _normalize_time_system(system_ref)
    if tok is None or tok in _KNOWN_BJD_TDB:
        if tok is None:
            key = "<missing>"
            if key not in _warned_unknown_tsys:
                _warned_unknown_tsys.add(key)
                print("  [to_bjd_tdb] pl_tsystemref missing - "
                      "assuming BJD_TDB (no conversion).")
        return float(t0_value)

    # The original observation could be at any observatory on Earth.
    # Using the geocenter introduces ≤21 ms error vs. a real observatory,
    # negligible compared to typical pl_tranmid uncertainties.
    geocenter = EarthLocation.from_geocentric(0, 0, 0, unit=u.m)
    t = Time(float(t0_value), format="jd", scale="utc", location=geocenter)
    tgt = SkyCoord(ra=float(ra_deg) * u.deg, dec=float(dec_deg) * u.deg)

    if tok in _KNOWN_HJD:
        # HJD = observer_UTC + ltt_helio.  BJD_TDB = observer_TDB + ltt_bary.
        # Recover observer UTC by subtracting ltt_helio, then convert.
        ltt_bary  = t.light_travel_time(tgt, kind="barycentric").jd
        ltt_helio = t.light_travel_time(tgt, kind="heliocentric").jd
        observer_utc_jd = float(t0_value) - ltt_helio
        observer_tdb_jd = (Time(observer_utc_jd, format="jd", scale="utc")
                           .tdb.jd)
        return observer_tdb_jd + ltt_bary

    if tok in _KNOWN_JD_UTC:
        # JD_UTC at observer → BJD_TDB.
        ltt_bary = t.light_travel_time(tgt, kind="barycentric").jd
        return t.tdb.jd + ltt_bary

    if tok not in _warned_unknown_tsys:
        _warned_unknown_tsys.add(tok)
        print(f"  [to_bjd_tdb] unknown pl_tsystemref={tok!r} - "
              "assuming BJD_TDB (no conversion).")
    return float(t0_value)


# ================================================================== #
#  4. TRANSIT GEOMETRY - Winn (2010)                                  #
# ================================================================== #
def compute_transit_geometry(row):
    """
    Compute primary transit and secondary eclipse geometry.

    Uses Winn (2010) arXiv:1001.2010:
      Eq. 14-15 for T14/T23, Eq. 16 for ecc correction, Eq. 33 for phi_sec.

    Omega convention: NEA pl_orblper = omega_planet.
    Winn uses omega_star = omega_planet + 180 deg.
    """
    P = row["pl_orbper"]                             # days

    # --- eccentricity & omega ---
    ecc = row.get("pl_orbeccen", np.nan)
    if pd.isna(ecc) or ecc < 0:
        ecc = 0.0
    omega_planet = row.get("pl_orblper", np.nan)
    if pd.isna(omega_planet):
        omega_planet = 0.0
    omega_star = omega_planet + 180.0                # Winn convention
    omega_rad = np.radians(omega_star)

    # --- stellar / planetary radii ---
    st_rad = row.get("st_rad", np.nan)               # R_Sun
    pl_rade = row.get("pl_rade", np.nan)              # R_Earth
    st_mass = row.get("st_mass", np.nan)              # M_Sun

    # --- semi-major axis ---
    a_AU = row.get("pl_orbsmax", np.nan)
    if pd.isna(a_AU) and pd.notna(st_mass) and st_mass > 0:
        a_AU = ((P / 365.25) ** 2 * st_mass) ** (1.0 / 3.0)

    # If we still can't compute geometry, try pl_trandur as fallback
    if pd.isna(a_AU) or pd.isna(st_rad) or st_rad <= 0:
        trandur = row.get("pl_trandur", np.nan)      # hours from catalog
        t14_h = trandur if pd.notna(trandur) and trandur > 0 else 2.0
        half_ph = (t14_h / 24.0) / (2.0 * P)
        phi_sec = 0.5
        if ecc > 0:
            phi_sec += (2.0 / np.pi) * ecc * np.cos(omega_rad) \
                       / np.sqrt(1.0 - ecc ** 2)
        return {
            "t14_h": t14_h, "t23_h": t14_h * 0.8,
            "half_ph": half_ph,
            "phi_sec": phi_sec,
            "t14_sec_h": t14_h,
            "half_ph_sec": half_ph,
            "b": 0.0, "ecc": ecc, "omega_star_deg": omega_star,
            "a_Rs": np.nan, "k": np.nan, "grazing": False,
        }

    a_Rs = a_AU / (st_rad * _R_SUN_AU)

    k = 0.01                                          # default Rp/R*
    if pd.notna(pl_rade) and pl_rade > 0:
        k = pl_rade * _R_EARTH_RSUN / st_rad

    # --- impact parameter ---
    incl = row.get("pl_orbincl", np.nan)
    if pd.isna(incl):
        b = 0.0
        incl = 90.0
    else:
        cos_i = np.cos(np.radians(incl))
        if ecc > 0:
            ecc_b = (1.0 - ecc ** 2) / (1.0 + ecc * np.sin(omega_rad))
        else:
            ecc_b = 1.0
        b = a_Rs * cos_i * ecc_b

    sin_i = np.sin(np.radians(incl))
    if sin_i == 0:
        sin_i = 1e-10

    # --- T14 (Eq. 14) ---
    arg14 = np.sqrt((1.0 + k) ** 2 - b ** 2) / (a_Rs * sin_i)
    arg14 = np.clip(arg14, -1.0, 1.0)
    T14_circ = (P / np.pi) * np.arcsin(arg14)         # days

    # --- T23 (Eq. 15) ---
    grazing = (1.0 - k) ** 2 - b ** 2 <= 0
    if not grazing:
        arg23 = np.sqrt((1.0 - k) ** 2 - b ** 2) / (a_Rs * sin_i)
        arg23 = np.clip(arg23, -1.0, 1.0)
        T23_circ = (P / np.pi) * np.arcsin(arg23)
    else:
        T23_circ = 0.0

    # --- eccentricity correction (Eq. 16) ---
    sqrt_1me2 = np.sqrt(1.0 - ecc ** 2) if ecc < 1 else 1.0
    ecc_prim = sqrt_1me2 / (1.0 + ecc * np.sin(omega_rad))
    ecc_sec = sqrt_1me2 / (1.0 - ecc * np.sin(omega_rad))

    T14 = T14_circ * ecc_prim
    T23 = T23_circ * ecc_prim
    T14_sec = T14_circ * ecc_sec

    # --- secondary eclipse phase (Eq. 33) ---
    phi_sec = 0.5
    if ecc > 0 and sqrt_1me2 > 0:
        phi_sec += (2.0 / np.pi) * ecc * np.cos(omega_rad) / sqrt_1me2

    # --- phase half-widths ---
    half_ph = T14 / (2.0 * P)
    half_ph_sec = T14_sec / (2.0 * P)

    return {
        "t14_h": T14 * 24.0,
        "t23_h": T23 * 24.0,
        "half_ph": half_ph,
        "phi_sec": phi_sec,
        "t14_sec_h": T14_sec * 24.0,
        "half_ph_sec": half_ph_sec,
        "b": b,
        "ecc": ecc,
        "omega_star_deg": omega_star,
        "a_Rs": a_Rs,
        "k": k,
        "grazing": bool(grazing),
    }


# ================================================================== #
#  5. EVENT PHASE WINDOWS                                             #
# ================================================================== #
def compute_event_windows(geom):
    """
    Phase windows for transit, pre-eclipse, post-eclipse.
    Phases in [0, 1).  Transit wraps around 0.
    """
    half_ph = geom["half_ph"]
    phi_sec = geom["phi_sec"]
    half_ph_sec = geom["half_ph_sec"]

    windows = {
        "transit": [(1.0 - half_ph, 1.0), (0.0, half_ph)],
        "pre_eclipse": [],
        "post_eclipse": [],
    }

    pre_start = 0.25
    pre_end = phi_sec - half_ph_sec
    if pre_end > pre_start:
        windows["pre_eclipse"] = [(pre_start, pre_end)]

    post_start = phi_sec + half_ph_sec
    post_end = 0.75
    if post_end > post_start:
        windows["post_eclipse"] = [(post_start, post_end)]

    return windows


# ================================================================== #
#  6. NIGHT COMPUTATION                                               #
# ================================================================== #
def compute_all_nights(target, obs, date_range, constraints,
                       resolution_min=2):
    """
    Compute observable windows for every night in date_range.

    Parameters
    ----------
    target : dict  {name, ra_deg, dec_deg, period, t0_bjd}
    obs    : dict  {lat, lon, alt, name}
    date_range : dict {start, end}  YYYY-MM-DD
    constraints : dict {min_target_alt, max_sun_alt, moon_dist_factor}
    resolution_min : int  grid resolution in minutes

    Returns
    -------
    List of night dicts.
    """
    loc = EarthLocation(lat=obs["lat"] * u.deg,
                        lon=obs["lon"] * u.deg,
                        height=obs["alt"] * u.m)
    tgt = SkyCoord(ra=target["ra_deg"] * u.deg,
                   dec=target["dec_deg"] * u.deg)

    d_start = Time(date_range["start"] + "T12:00:00", scale="utc")
    d_end = Time(date_range["end"] + "T12:00:00", scale="utc")
    n_days = int(d_end.jd - d_start.jd) + 1

    # UTC offset from longitude (approximate local midnight)
    utc_off_h = obs["lon"] / 15.0

    # Night centers (local midnight in UTC JD)
    night_centers_jd = d_start.jd + np.arange(n_days) + (12.0 - utc_off_h) / 24.0

    # Time grid: ±7h from center
    n_pts = int(14 * 60 / resolution_min) + 1
    offsets_h = np.linspace(-7, 7, n_pts)
    offsets_d = offsets_h / 24.0

    min_alt = constraints["min_target_alt"]
    max_sun = constraints["max_sun_alt"]
    moon_factor = constraints["moon_dist_factor"]

    P = target["period"]
    T0 = target["t0_bjd"]

    nights = []

    for i in range(n_days):
        jd_center = night_centers_jd[i]
        grid_jd = jd_center + offsets_d
        times = Time(grid_jd, format="jd", scale="utc")

        # Date string for this night (UT date at night center)
        date_str = (Time(jd_center, format="jd", scale="utc")
                    .to_datetime().strftime("%Y-%m-%d"))

        frame = AltAz(obstime=times, location=loc)

        # Target altitude
        tgt_altaz = tgt.transform_to(frame)
        target_alt = tgt_altaz.alt.deg

        # Sun altitude
        sun_coord = get_sun(times)
        sun_altaz = sun_coord.transform_to(frame)
        sun_alt = sun_altaz.alt.deg

        # Moon
        moon_coord = get_body("moon", times, loc)
        moon_altaz = moon_coord.transform_to(frame)
        moon_alt = moon_altaz.alt.deg

        # Moon at night center
        nc_idx = n_pts // 2
        moon_sep = moon_coord[nc_idx].separation(tgt).deg
        moon_sun_elo = moon_coord[nc_idx].separation(sun_coord[nc_idx]).rad
        moon_illum = (1.0 - np.cos(moon_sun_elo)) / 2.0

        moon_ok = ((moon_sep > moon_factor * moon_illum * 100.0)
                   or (moon_alt[nc_idx] < 0))

        # Observable mask
        obs_mask = (target_alt > min_alt) & (sun_alt < max_sun)
        has_obs = obs_mask.any()

        # Barycentric correction → BJD_TDB
        tdb_off = times.tdb.jd - times.jd
        ltt = times.light_travel_time(tgt, location=loc).jd
        bjd_tdb = times.jd + tdb_off + ltt

        # Phase
        phases = ((bjd_tdb - T0) / P) % 1.0

        nights.append({
            "date_str": date_str,
            "has_obs": bool(has_obs),
            "times_jd": grid_jd,
            "times_utc": times,
            "target_alt": target_alt,
            "sun_alt": sun_alt,
            "moon_alt": moon_alt,
            "moon_illum": float(moon_illum),
            "moon_sep": float(moon_sep),
            "moon_ok": bool(moon_ok),
            "bjd_tdb": bjd_tdb,
            "phases": phases,
            "obs_mask": obs_mask,
        })

    return nights


# ================================================================== #
#  7. EVENT MATCHING - wrapped interval intersection                  #
# ================================================================== #
def _interval_width(intervals):
    """Sum of widths of non-wrapping intervals."""
    return sum(e - s for s, e in intervals)


def _interval_intersection_width(intervals_a, intervals_b):
    """Total intersection width between two sets of [start, end) intervals."""
    total = 0.0
    for a_s, a_e in intervals_a:
        for b_s, b_e in intervals_b:
            lo = max(a_s, b_s)
            hi = min(a_e, b_e)
            if hi > lo:
                total += hi - lo
    return total


def _observable_phase_intervals(phases, obs_mask):
    """
    Extract non-wrapping phase intervals from an observable mask.
    Split at phase discontinuities > 0.5 (wrap-around).
    """
    idx = np.where(obs_mask)[0]
    if len(idx) == 0:
        return []

    ph = phases[idx]
    intervals = []
    seg_start = ph[0]
    prev = ph[0]

    for k in range(1, len(ph)):
        diff = ph[k] - prev
        if abs(diff) > 0.5:
            # Phase wrapped - extend to boundary for continuity
            if prev > 0.5:
                intervals.append((seg_start, 1.0))
            else:
                intervals.append((seg_start, prev))
            if ph[k] < 0.5:
                seg_start = 0.0
            else:
                seg_start = ph[k]
        prev = ph[k]
    intervals.append((seg_start, prev))

    # Fix segments where start > end (actual wrap within segment)
    fixed = []
    for s, e in intervals:
        if s <= e:
            fixed.append((s, e))
        else:
            fixed.append((s, 1.0))
            fixed.append((0.0, e))
    return fixed


def match_events(night, event_windows, event_constraints, geom):
    """
    For one observable night, check which events are schedulable.

    Returns list of event dicts.
    """
    if not night["has_obs"]:
        return []

    obs_intervals = _observable_phase_intervals(
        night["phases"], night["obs_mask"])
    if not obs_intervals:
        return []

    results = []
    for event_type, evt_intervals in event_windows.items():
        if not evt_intervals:
            continue

        evt_width = _interval_width(evt_intervals)
        if evt_width <= 0:
            continue

        inter_width = _interval_intersection_width(obs_intervals, evt_intervals)
        coverage = inter_width / evt_width

        min_cov = event_constraints.get(event_type, {}).get("min_coverage", 1.0)
        if coverage < min_cov:
            continue

        # Find UT times and altitude at midpoint of the intersection
        in_event_mask = np.zeros(len(night["phases"]), dtype=bool)
        for s, e in evt_intervals:
            if s <= e:
                in_event_mask |= ((night["phases"] >= s) & (night["phases"] <= e))
            else:
                in_event_mask |= ((night["phases"] >= s) | (night["phases"] <= e))

        combined = night["obs_mask"] & in_event_mask
        idx_combined = np.where(combined)[0]
        if len(idx_combined) == 0:
            continue

        i_start = idx_combined[0]
        i_end = idx_combined[-1]
        i_mid = idx_combined[len(idx_combined) // 2]

        ut_start = night["times_utc"][i_start].iso
        ut_end = night["times_utc"][i_end].iso
        alt_mid = float(night["target_alt"][i_mid])
        phase_mid = float(night["phases"][i_mid])

        results.append({
            "event_type": event_type,
            "coverage": float(coverage),
            "phase_start": float(night["phases"][i_start]),
            "phase_end": float(night["phases"][i_end]),
            "phase_mid": phase_mid,
            "ut_start": ut_start,
            "ut_end": ut_end,
            "alt_at_midpoint": alt_mid,
        })

    return results


# ================================================================== #
#  MAIN                                                               #
# ================================================================== #
def main():
    from phase_config import (
        CATALOG_SOURCE, CATALOG_DIR,
        DESERT_FILTER, EXTRA_FILTERS, OBSERVATORY,
        DATE_RANGE, CONSTRAINTS, EVENT_CONSTRAINTS, TIME_RESOLUTION_MIN,
        OUTPUT_DIR, DESERT_BOUNDARY_FILE, KDE_FILE, P_MAX, R_MAX,
        FETCH_NEA_ONLINE, NEA_FETCH_TIMEOUT, PRESELECTION_MIN_YEAR,
        SKY_TRANSMISSION_FITS, TELLURIC_LAMBDA_RANGE_NM,
        TELLURIC_RV_GRID_KMS, TELLURIC_PAD_HOURS, TELLURIC_EXP_TIME_S,
    )
    from nea_fetch import resolve_catalog_path
    from phase_plotter import plot_event, plot_calendar, plot_PR_landscape
    from phase_summary import (compute_planet_metrics, render_planet_summary,
                                compute_kp)
    from phase_telluric_plot import plot_telluric_position

    LIMIT_RADIUS = 1.5 # None
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Load + filter catalog
    print("\n» [1/5] Loading catalog")
    print(f"  source = {CATALOG_SOURCE}")
    polygon = load_desert_polygon(DESERT_BOUNDARY_FILE)
    csv_path = resolve_catalog_path(
        source=CATALOG_SOURCE,
        online=FETCH_NEA_ONLINE,
        catalog_dir=CATALOG_DIR,
        timeout=NEA_FETCH_TIMEOUT,
    )
    df = load_catalog(csv_path, source=CATALOG_SOURCE)
    print(f"  {len(df)} rows ({df['pl_name'].nunique()} planets) from {csv_path}")

    # Oldest publication date per planet (across all rows in the raw PS
    # table) - used to gate PRESELECTION inclusion.
    if "pl_pubdate" in df.columns:
        oldest_pubdate = df.groupby("pl_name")["pl_pubdate"].min()
    else:
        oldest_pubdate = pd.Series(dtype="datetime64[ns]")

    # Qualifying planets are collected here and written to a single
    # OUTPUT_DIR/preselection.csv at the end (no symlink farm, no duplicated
    # files: the per-planet outputs stay only in their base folders).
    preselection_rows = []

    # Merge per-planet first so EXTRA_FILTERS sees the best available
    # value for each field (e.g. pl_rade pulled from a non-ephemeris paper
    # when the ephemeris paper is TTV-only).
    print("\n» [2/5] Filtering catalog")
    df_composite = compose_best_rows(df)
    print(f"  Composed: {len(df_composite)} planets from {len(df)} rows")

    df_best = filter_catalog(df_composite, DESERT_FILTER, polygon, EXTRA_FILTERS)
    print(f"  After filters: {len(df_best)} planets")

    if df_best.empty and not CUSTOM_PLANETS:
        print("  No planets to schedule - exiting.")
        return df, df_best, []

    show = ["pl_name", "pl_orbper", "pl_rade", "pl_tranmid", "ra", "dec"]
    show = [c for c in show if c in df_best.columns]
    print(df_best[show].to_string(index=False))

    # 2. Per planet: geometry + nights + events
    print("\n» [3/5] Scheduling planets")
    all_events = []

    # ── Inject CUSTOM_PLANETS from config ─────────────────────────
    # When a custom entry shares its pl_name with a catalog row, the catalog
    # row is taken as the base and only the fields the user explicitly listed
    # in CUSTOM_PLANETS override it.  This keeps catalog-derived parameters
    # (st_mass, pl_orbincl, pl_orbsmax, pl_orbeccen, …) intact, so downstream
    # quantities like Kp still compute, while still letting v_sys / mass /
    # ephemeris be overridden per planet.
    if CUSTOM_PLANETS:
        _mag_map = {"st_jmag": "sy_jmag", "st_kmag": "sy_kmag"}
        custom_names = {cp.get("pl_name") for cp in CUSTOM_PLANETS
                        if cp.get("pl_name")}
        catalog_by_name = {}
        if "pl_name" in df_best.columns:
            for _, r in df_best[df_best["pl_name"].isin(custom_names)].iterrows():
                catalog_by_name[r["pl_name"]] = r.to_dict()

        _rows = []
        n_merged = 0
        for cp in CUSTOM_PLANETS:
            override = {_mag_map.get(k, k): v for k, v in cp.items()}
            base = catalog_by_name.get(cp.get("pl_name"))
            if base is not None:
                row = {**base, **override}  # custom wins per field
                row["catalog_source"] = "custom+nea"
                n_merged += 1
            else:
                row = override
                row.setdefault("catalog_source", "custom")
            row.setdefault("_ref_label", "custom")
            row.setdefault("_ref_rank", 1)
            row.setdefault("_param_fallback", 0)
            _rows.append(row)

        df_custom = pd.DataFrame(_rows)
        df_best = df_best[~df_best["pl_name"].isin(custom_names)]
        df_best = pd.concat([df_best, df_custom], ignore_index=True)
        print(f"\n  ✔  {len(_rows)} pianeti custom iniettati da config.py "
              f"({n_merged} mergiati con righe di catalogo)")

    for _, row in df_best.iterrows():
        name = row["pl_name"]
        print(f"\n{'=' * 60}")
        print(f"  ● {name}")
        print(f"{'=' * 60}")

        geom = compute_transit_geometry(row)
        print(f"  T14 = {geom['t14_h']:.2f} h  |  "
              f"phi_sec = {geom['phi_sec']:.4f}  |  "
              f"ecc = {geom['ecc']:.4f}")

        windows = compute_event_windows(geom)
        for etype, ints in windows.items():
            if ints:
                w = _interval_width(ints)
                print(f"  {etype:15s}: {ints}  (width={w:.5f})")

        # Compute TSM/ESM (and Simbad mags + scale heights) BEFORE
        # creating the planet directory, so the folder name can carry
        # _TSM / _ESM / _TSM_ESM tags reflecting the Kempton checks.
        try:
            metrics = compute_planet_metrics(row)
        except Exception as e:
            print(f"  ⚠  metrics compute failed for {name}: {e}")
            metrics = {"mags": None, "tsm_row": None, "sh": None}

        tsm_row = metrics.get("tsm_row") or {}
        suffix_parts = []
        if tsm_row.get("TSM_above"):
            suffix_parts.append("TSM")
        if tsm_row.get("ESM_above"):
            suffix_parts.append("ESM")
        suffix = ("_" + "_".join(suffix_parts)) if suffix_parts else ""

        safe_name = name.replace(" ", "_")
        planet_dir = os.path.join(OUTPUT_DIR, safe_name + suffix)

        try:
            summary_path = render_planet_summary(row, metrics, planet_dir,
                                                 geom=geom)
            print(f"  summary → {summary_path}")
        except Exception as e:
            print(f"  ⚠  summary card failed for {name}: {e}")

        # ── PRESELECTION: collect qualifying planets for preselection.csv ──
        oldest_pd = oldest_pubdate.get(name) if len(oldest_pubdate) else None
        qualifies_year = (pd.notna(oldest_pd)
                          and oldest_pd.year > PRESELECTION_MIN_YEAR)
        qualifies_metrics = (bool(tsm_row.get("TSM_above"))
                             or bool(tsm_row.get("ESM_above")))
        if qualifies_year and qualifies_metrics:
            preselection_rows.append({
                "pl_name":        name,
                "hostname":       row.get("hostname"),
                "folder":         os.path.basename(planet_dir),
                "pub_year":       oldest_pd.year,
                "ra_deg":         row.get("ra"),
                "dec_deg":        row.get("dec"),
                "period_days":    tsm_row.get("Period_days"),
                "Rp_Rearth":      tsm_row.get("Rp_Rearth"),
                "Mp_Mearth":      tsm_row.get("Mp_Mearth"),
                "Teq_K":          tsm_row.get("Teq_K"),
                "density_gcm3":   tsm_row.get("density_gcm3"),
                "category":       tsm_row.get("category"),
                "T14_h":          geom.get("t14_h"),
                "TSM":            tsm_row.get("TSM"),
                "TSM_threshold":  tsm_row.get("TSM_threshold"),
                "TSM_above":      tsm_row.get("TSM_above"),
                "ESM":            tsm_row.get("ESM"),
                "ESM_threshold":  tsm_row.get("ESM_threshold"),
                "ESM_above":      tsm_row.get("ESM_above"),
                "Rs_Rsun":        tsm_row.get("Rs_Rsun"),
                "Teff_star":      tsm_row.get("Teff_star"),
                "mag_J":          tsm_row.get("mag_J"),
                "mag_K":          tsm_row.get("mag_K"),
            })

        ra_deg  = float(row["ra"])
        dec_deg = float(row["dec"])
        t0_raw  = float(row["pl_tranmid"])
        tsys    = row.get("pl_tsystemref")
        t0_bjd  = to_bjd_tdb(t0_raw, tsys, ra_deg, dec_deg)
        delta_s = (t0_bjd - t0_raw) * 86400.0
        print(f"  T0 system: {tsys!r} → BJD_TDB; Δ = {delta_s:+.2f} s")

        # vsys for telluric-position plot: prefer per-target user override,
        # fall back to NEA st_radv. None when neither is finite.
        v_sys_user = row.get("v_sys")
        v_sys_cat = row.get("st_radv")
        v_sys_pick = v_sys_user if pd.notna(v_sys_user) else v_sys_cat
        v_sys_kms = float(v_sys_pick) if pd.notna(v_sys_pick) else None

        # Planet RV semi-amplitude Kp: needed for the telluric plot's
        # planet-RV band. Falls back to None if period / st_mass / mass missing.
        try:
            kp_kms = compute_kp(row, tsm_row)
        except Exception as exc:
            print(f"  ⚠  Kp compute failed for {name}: {exc}")
            kp_kms = None

        target = {
            "name": name,
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "period": float(row["pl_orbper"]),
            "t0_bjd": t0_bjd,
            "v_sys_kms": v_sys_kms,
            "kp_kms": kp_kms,
        }

        print(f"  Computing nights ({DATE_RANGE['start']} → "
              f"{DATE_RANGE['end']})...")
        nights = compute_all_nights(
            target, OBSERVATORY, DATE_RANGE, CONSTRAINTS,
            TIME_RESOLUTION_MIN)

        n_obs = sum(1 for n in nights if n["has_obs"])
        print(f"  {len(nights)} nights, {n_obs} observable")

        planet_events = []
        for n in nights:
            if not n["has_obs"]:
                continue
            evts = match_events(n, windows, EVENT_CONSTRAINTS, geom)
            for e in evts:
                e["planet"] = name
                e["date"] = n["date_str"]
                e["moon_illum"] = n["moon_illum"]
                e["moon_sep"] = n["moon_sep"]
                e["moon_ok"] = n["moon_ok"]
                # Store references for plotter (not saved to CSV)
                e["_night"] = n
                e["_geom"] = geom
                e["_target"] = target
                e["_windows"] = windows
                e["_row"] = row
                e["_planet_dir"] = planet_dir
                planet_events.append(e)

        # Save per-planet CSV
        if planet_events:
            os.makedirs(planet_dir, exist_ok=True)
            csv_rows = [{k: v for k, v in e.items()
                         if not k.startswith("_")}
                        for e in planet_events]
            pd.DataFrame(csv_rows).to_csv(
                os.path.join(planet_dir, "events_summary.csv"),
                index=False)

            counts = {}
            for e in planet_events:
                counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
            for et, c in sorted(counts.items()):
                print(f"  {et}: {c} events")

        all_events.extend(planet_events)

    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {len(all_events)} events across "
          f"{len(df_best)} planets")
    print(f"{'=' * 60}")

    # Write the preselection table (recent + TSM/ESM above threshold).
    if preselection_rows:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        preselection_csv = os.path.join(OUTPUT_DIR, "preselection.csv")
        pd.DataFrame(preselection_rows).to_csv(preselection_csv, index=False)
        print(f"  PRESELECTION → {preselection_csv} "
              f"({len(preselection_rows)} planets)")

    if not all_events:
        return df, df_best, all_events

    # --- P-R landscape ---
    print("\n» [4/5] Generating P-R landscape")
    df_unique = (df.sort_values("pl_pubdate", ascending=False)
                 .drop_duplicates("pl_name", keep="first"))
    plot_PR_landscape(df_unique, df_best, DESERT_BOUNDARY_FILE,
                      KDE_FILE, P_MAX, R_MAX, OUTPUT_DIR)

    # --- Per planet: calendars + individual event plots ---
    grouped = {}
    for e in all_events:
        grouped.setdefault(e["planet"], []).append(e)

    for planet_name, planet_events in grouped.items():
        planet_dir = planet_events[0]["_planet_dir"]
        obs_label = OBSERVATORY["name"].replace(" ", "_")

        # Calendar per event type
        for etype in ("transit", "pre_eclipse", "post_eclipse"):
            typed = [e for e in planet_events
                     if e["event_type"] == etype]
            if typed:
                cal_path = os.path.join(
                    planet_dir, f"calendar_{etype}.pdf")
                plot_calendar(typed, etype, planet_name,
                              typed[0]["_windows"], cal_path)
                print(f"  Calendar: {cal_path}")

        # Multi-page PDF per event type: one page per event, sorted by date.
        from matplotlib.backends.backend_pdf import PdfPages
        for etype in ("transit", "pre_eclipse", "post_eclipse"):
            typed = sorted((e for e in planet_events
                            if e["event_type"] == etype),
                           key=lambda e: e["date"])
            if not typed:
                continue
            out_path = os.path.join(planet_dir, f"{etype}.pdf")
            with PdfPages(out_path) as pdf:
                for e in typed:
                    plot_event(e, OBSERVATORY, pdf=pdf)
                    plot_telluric_position(
                        e, OBSERVATORY, e["_target"],
                        vsys_kms      = e["_target"]["v_sys_kms"],
                        kp_kms        = e["_target"].get("kp_kms"),
                        sky_fits_path = SKY_TRANSMISSION_FITS,
                        lam_range_nm  = TELLURIC_LAMBDA_RANGE_NM,
                        rv_grid_kms   = TELLURIC_RV_GRID_KMS,
                        pad_hours     = TELLURIC_PAD_HOURS,
                        exp_time_s    = TELLURIC_EXP_TIME_S,
                        pdf           = pdf,
                    )
            print(f"  {etype}.pdf: {len(typed)} pages → {out_path}")

        print(f"  {len(planet_events)} event plots for {planet_name}")

    print("\n» [5/5] Done")
    print(f"  {len(df_best)} planets · {len(all_events)} events · "
          f"output → {OUTPUT_DIR}")
    return df, df_best, all_events


if __name__ == "__main__":
    main()
