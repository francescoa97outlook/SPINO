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
# level, negligible for visibility/airmass, so silence just this message
# (matched by text, to avoid muting unrelated AstropyWarnings).
warnings.filterwarnings(
    "ignore",
    message=r".*polar motion.*",
    category=AstropyWarning,
)

from phase_config import CUSTOM_PLANETS
import phase_kepler
from nea_fetch import limit_flag
from phase_stellar_rv import resolve_systemic_velocity

# Targets already warned about a given geometry caveat (missing omega,
# non-transiting composite geometry, silent trandur fallback, ...), so each
# distinct message appears once per (target, caveat) instead of once per
# computed night.  Keyed by (planet_name, warning_key); the bare planet_name
# string is also accepted for backward compatibility with existing callers
# and tests that only care about the omega warning.
_geom_omega_warned: set = set()


def _warn_geom_once(planet_name, warning_key: str, msg: str) -> None:
    key = (str(planet_name), warning_key)
    if key in _geom_omega_warned:
        return
    _geom_omega_warned.add(key)
    print(f"  ⚠  {msg}")


def _warn_geom_omega_once(planet_name, msg: str) -> None:
    _warn_geom_once(planet_name, "omega", msg)

# ================================================================== #
#  CONSTANTS                                                          #
# ================================================================== #
_R_SUN_AU = 0.00465047                    # R_Sun in AU
_R_EARTH_RSUN = 6.371e6 / 6.957e8        # R_Earth / R_Sun
RJUP_TO_REARTH = 11.209                   # R_Jup / R_Earth
ORBSMAX_KEPLER_TOL = 0.25                 # max |a/a_kepler - 1| before rejecting a donor

# Below this shift the eclipse timing is treated as circular.  A time
# tolerance rather than a bare eccentricity cut: e = 0.01 alone already
# shifts the eclipse ~27 min at P = 3 d, well past what "circular" should
# mean for minute-level scheduling.
_ECC_TIMING_TOL_D = 60.0 / 86400.0        # 1 minute, in days
_AU_LIGHT_S = 499.004784                  # light-travel time for 1 AU [s] (IAU tau_A)


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


def _a_from_kepler(P_days, st_mass):
    """Semi-major axis [AU] from Kepler's 3rd law, or NaN if inputs missing."""
    if pd.isna(P_days) or pd.isna(st_mass) or st_mass <= 0:
        return np.nan
    return ((P_days / 365.25) ** 2 * st_mass) ** (1.0 / 3.0)


def _reconcile_orbsmax(composite, sources, group) -> bool:
    """
    Cross-check ``composite['pl_orbsmax']`` against Kepler's 3rd law.

    ``compose_best_rows`` fills every field independently from the most
    recent reference that reports it, so ``pl_orbsmax`` can end up paired
    with a ``pl_orbincl``/``st_rad``/``pl_rade`` combination from *other*
    references it was never measured against.  A semi-major axis that is
    wildly inconsistent with P and M* (via a = ((P/365.25)^2 * M*)^(1/3))
    is a strong sign of exactly that mismatch, and downstream it can make
    ``compute_transit_geometry`` require sqrt() of a negative number.

    Walks ``group`` (already pubdate-desc sorted) and accepts the most
    recent donor whose ``pl_orbsmax`` agrees with the Kepler estimate to
    within ``ORBSMAX_KEPLER_TOL``.  If none agrees, falls back to the
    Kepler estimate itself.  Returns True iff an existing (already-filled)
    value was overridden -- i.e. an actual inconsistency was found and
    corrected, as opposed to silently filling a field no donor had.
    """
    P = composite.get("pl_orbper")
    st_mass = composite.get("st_mass")
    a_kepler = _a_from_kepler(P, st_mass)
    if pd.isna(a_kepler) or "pl_orbsmax" not in group.columns:
        return False

    current_a = composite.get("pl_orbsmax")
    current_ref = sources.get("pl_orbsmax", "")

    accepted = None
    for _, cand in group[group["pl_orbsmax"].notna()].iterrows():
        a = cand["pl_orbsmax"]
        if pd.notna(a) and abs(a / a_kepler - 1.0) <= ORBSMAX_KEPLER_TOL:
            accepted = cand
            break

    name = composite.get("pl_name", "?")
    had_value = pd.notna(current_a)

    if accepted is not None:
        a = accepted["pl_orbsmax"]
        ref = accepted.get("pl_refname", "")
        corrected = had_value and (pd.isna(current_a) or a != current_a)
        if corrected:
            print(f"  [compose_best_rows] {name}: pl_orbsmax={current_a:.4g} AU "
                  f"from {current_ref!r} incompatible with Kepler's 3rd law "
                  f"(a_kepler={a_kepler:.4g} AU); using {ref!r} "
                  f"(a={a:.4g} AU) instead")
        composite["pl_orbsmax"] = a
        composite["pl_orbsmaxerr1"] = accepted.get("pl_orbsmaxerr1", np.nan)
        composite["pl_orbsmaxerr2"] = accepted.get("pl_orbsmaxerr2", np.nan)
        sources["pl_orbsmax"] = ref
        return corrected

    # No reference's pl_orbsmax agrees with Kepler; fall back to the
    # Kepler estimate itself rather than keep a value known to be wrong.
    if had_value:
        print(f"  [compose_best_rows] {name}: pl_orbsmax={current_a:.4g} AU "
              f"from {current_ref!r} incompatible with Kepler's 3rd law and no "
              f"other reference agrees; using a_kepler={a_kepler:.4g} AU")
    composite["pl_orbsmax"] = a_kepler
    composite["pl_orbsmaxerr1"] = np.nan
    composite["pl_orbsmaxerr2"] = np.nan
    sources["pl_orbsmax"] = "Kepler's 3rd law"
    return had_value


_EPHEMERIS_FIELDS = (
    "pl_orbper", "pl_orbpererr1", "pl_orbpererr2",
    "pl_tranmid", "pl_tranmiderr1", "pl_tranmiderr2",
    "pl_tsystemref",
)
_OTHER_FIELDS = (
    "ra", "dec",
    "pl_orbsmax", "pl_orbsmaxerr1", "pl_orbsmaxerr2",
    "pl_orbincl", "pl_imppar",
    "pl_rade", "pl_radeerr1", "pl_radeerr2",
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


_MASS_FIELDS = ("pl_bmasse", "pl_bmasseerr1", "pl_bmasseerr2")


def _compose_orbit_shape(group, composite, sources):
    """
    Eccentricity and argument of periastron are fitted together, so both come
    from one reference: the most recent that reports an eccentricity, as a
    measurement or as an upper limit (``pl_orbeccenlim`` = 1, kept in the
    composite so that the geometry can decide what to do with it).  A lower
    limit says too little about the orbit to be used and is skipped.  The
    donor's omega is adopted only if that same reference reports it as a
    value; omega is never borrowed from a different solution.

    ``group`` must already be sorted by publication date, newest first.
    """
    composite["pl_orbeccen"] = np.nan
    composite["pl_orbeccenlim"] = 0
    composite["pl_orblper"] = np.nan
    if "pl_orbeccen" not in group.columns:
        return

    for _, cand in group[group["pl_orbeccen"].notna()].iterrows():
        lim = limit_flag(cand.get("pl_orbeccenlim"))
        if lim not in (0, 1):
            continue
        ref = cand.get("pl_refname", "")
        composite["pl_orbeccen"] = cand["pl_orbeccen"]
        composite["pl_orbeccenlim"] = lim
        sources["pl_orbeccen"] = ref
        omega = cand.get("pl_orblper", np.nan)
        if pd.notna(omega) and limit_flag(cand.get("pl_orblperlim")) == 0:
            composite["pl_orblper"] = omega
            sources["pl_orblper"] = ref
        return


def _compose_mass(group, composite, sources):
    """
    A measured planetary mass is preferred to a more recent limit.  An upper
    limit is used only when no reference measures the mass, and is flagged
    (``pl_bmasselim`` = 1) so that the summary card can mark the mass and the
    metrics computed from it.  Lower limits are not used.
    """
    for f in _MASS_FIELDS:
        composite[f] = np.nan
    composite["pl_bmasselim"] = 0
    if "pl_bmasse" not in group.columns:
        return

    cands = group[group["pl_bmasse"].notna()]
    if "pl_bmasselim" in cands.columns:
        flags = cands["pl_bmasselim"].map(limit_flag)
    else:
        flags = pd.Series(0, index=cands.index)
    for wanted in (0, 1):
        pick = cands[flags == wanted]
        if pick.empty:
            continue
        donor = pick.iloc[0]
        for f in _MASS_FIELDS:
            if f in donor.index:
                composite[f] = donor[f]
        composite["pl_bmasselim"] = wanted
        sources["pl_bmasse"] = donor.get("pl_refname", "")
        return


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
        non-null value across this planet's rows, with two exceptions:
        eccentricity and argument of periastron come together from one
        reference (`_compose_orbit_shape`), and the planetary mass prefers
        a measurement to a limit (`_compose_mass`).  The NEA limit flags of
        both travel with them as ``pl_orbeccenlim`` / ``pl_bmasselim``.
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
    n_orbsmax_reconciled = 0
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

        _compose_orbit_shape(group, composite, sources)
        _compose_mass(group, composite, sources)

        if _reconcile_orbsmax(composite, sources, group):
            n_orbsmax_reconciled += 1

        composite["pl_refname"] = ref_eph
        composite["_field_sources"] = sources
        rows_out.append(composite)

    if skipped:
        print(f"  [compose_best_rows] {skipped} planets skipped "
              "(no row with pl_orbper+pl_tranmid+ra+dec)")
    if n_orbsmax_reconciled:
        print(f"  [compose_best_rows] {n_orbsmax_reconciled} planets had "
              "pl_orbsmax reconciled against Kepler's 3rd law")

    out = pd.DataFrame(rows_out)
    return out.reset_index(drop=True)


# ================================================================== #
#  3.5  TIME-SCALE NORMALIZATION                                      #
# ================================================================== #
# Tokens as returned by _normalize_time_system (upper case, alphanumerics).
_KNOWN_BJD_TDB    = {"BJDTDB", "BJD",            # already barycentric-TDB;
                     "BJDTT", "BJDTBD"}          # TT is within 2 ms of TDB,
                                                 # TBD is a typo for TDB
_KNOWN_BJD_UTC    = {"BJDUTC", "UTCBJD"}         # barycentric, UTC scale
_KNOWN_BJD_TCB    = {"BJDTCB"}                   # barycentric, TCB scale
_KNOWN_HJD        = {"HJD", "HJDUTC"}            # heliocentric (UTC)
_KNOWN_HJD_TDB    = {"HJDTDB"}                   # heliocentric (TDB)
_KNOWN_JD_UTC     = {"JDUTC"}                    # geocentric UTC
# A bare "JD" labels many archive epochs that are already BJD_TDB.  On the
# 55 planets of the bundled snapshot that also have a precise BJD-TDB row,
# the JD-labelled epochs agree with it as published (median 0.3 min) and
# disagree once read as geocentric UTC (median 2.6 min), so they are taken
# as BJD_TDB.  Only an explicit "JD_UTC" is converted.
_JD_AS_BJD_TDB    = {"JD"}


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


def _note_tsys_once(key, msg):
    if key not in _warned_unknown_tsys:
        _warned_unknown_tsys.add(key)
        print(f"  [to_bjd_tdb] {msg}")


def to_bjd_tdb(t0_value, system_ref, ra_deg, dec_deg):
    """
    Convert ``t0_value`` (Julian Date in the time system named by
    ``system_ref``) to BJD_TDB.  Returns the converted JD as a float.

    Recognized values (NEA convention, matched case-insensitive after
    stripping non-alphanumerics):
      - BJD_TDB / BJD-TDB / BJD / BJD-TT / BJD-TBD : returned unchanged
      - JD                      : returned unchanged (see _JD_AS_BJD_TDB)
      - BJD_UTC / UTC-BJD       : add TDB-UTC
      - BJD_TCB                 : TCB → TDB
      - HJD / HJD_UTC           : add (BJD-HJD) using astropy
                                  light_travel_time barycentric/heliocentric,
                                  and TDB-UTC
      - HJD_TDB                 : add (BJD-HJD) only
      - JD_UTC                  : add (BJD-JD) ≈ (TDB-UTC) + barycentric ltt

    Missing/unknown system refs are treated as BJD_TDB with a one-time
    warning per token, and the value is returned unchanged.
    """
    if not pd.notna(t0_value):
        return t0_value

    tok = _normalize_time_system(system_ref)
    if tok is None:
        _note_tsys_once("<missing>", "pl_tsystemref missing; "
                        "assuming BJD_TDB (no conversion).")
        return float(t0_value)
    if tok in _KNOWN_BJD_TDB:
        return float(t0_value)
    if tok in _JD_AS_BJD_TDB:
        _note_tsys_once(tok, "pl_tsystemref='JD' read as BJD_TDB "
                        "(no conversion); only 'JD_UTC' is converted.")
        return float(t0_value)
    if tok in _KNOWN_BJD_UTC:
        return Time(float(t0_value), format="jd", scale="utc").tdb.jd
    if tok in _KNOWN_BJD_TCB:
        return Time(float(t0_value), format="jd", scale="tcb").tdb.jd

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

    if tok in _KNOWN_HJD_TDB:
        # Already on the TDB scale: only the heliocentric → barycentric step.
        ltt_bary  = t.light_travel_time(tgt, kind="barycentric").jd
        ltt_helio = t.light_travel_time(tgt, kind="heliocentric").jd
        return float(t0_value) - ltt_helio + ltt_bary

    if tok in _KNOWN_JD_UTC:
        # JD_UTC at observer → BJD_TDB.
        ltt_bary = t.light_travel_time(tgt, kind="barycentric").jd
        return t.tdb.jd + ltt_bary

    _note_tsys_once(tok, f"unknown pl_tsystemref={tok!r}; "
                    "assuming BJD_TDB (no conversion).")
    return float(t0_value)


# ================================================================== #
#  4. TRANSIT GEOMETRY: Winn (2010)                                  #
# ================================================================== #
def compute_transit_geometry(row, ecc_upper_limits_as_values=False):
    """
    Compute primary transit and secondary eclipse geometry.

    Uses Winn (2010) arXiv:1001.2010:
      Eq. 14-15 for T14/T23, Eq. 16 for the eccentricity duration
      correction (Eq. 8 for the occultation impact parameter b_occ).  The
      secondary-eclipse phase and quadratures are solved exactly through
      Kepler's equation (phase_kepler.secondary_eclipse_phase /
      quadrature_phases) instead of Winn's Eq. 33, which is first order in
      e and can be off by hours of phase at moderate eccentricity.

    Omega convention: NEA pl_orblper is stored as published, which for the
    radial-velocity solutions it comes from is omega_star, the argument of
    periastron of the star's reflex orbit; the transit falls at true anomaly
    pi/2 - omega_star (Winn 2010, Eq. 6), as the NEA Transit Service also
    assumes.  phase_kepler works with the planet's omega_p = omega_star + 180.

    An eccentricity that the catalogue gives only as an upper limit
    (``pl_orbeccenlim`` = 1) is treated as circular unless
    ``ecc_upper_limits_as_values`` is set, in which case the limit is used as
    the eccentricity; it is flagged ``ecc_upper_limit`` either way.
    """
    P = row["pl_orbper"]                             # days
    pname = row.get("pl_name", "?")

    # Every assumption this geometry rests on (missing eccentricity,
    # missing omega, eccentricity too small to matter, ...) is recorded
    # here and carried out to events_summary.csv as "geom_flags", so a
    # downstream consumer does not have to parse stderr to know what was
    # assumed.
    geom_flags = []

    # --- eccentricity & omega ---
    ecc_raw = row.get("pl_orbeccen", np.nan)
    ecc_missing = pd.isna(ecc_raw)
    ecc = 0.0 if (ecc_missing or ecc_raw < 0) else ecc_raw
    if not ecc_missing and limit_flag(row.get("pl_orbeccenlim")) == 1:
        geom_flags.append("ecc_upper_limit")
        if not ecc_upper_limits_as_values:
            ecc = 0.0
    omega_star_raw = row.get("pl_orblper", np.nan)
    omega_known = pd.notna(omega_star_raw)
    if not omega_known:
        # T14 depends on omega for an eccentric orbit, so falling back to 0 deg
        # is an assumption, not a neutral default.  Say so rather than let it
        # pass as a measured geometry.  On a circular orbit omega drops out of
        # every expression below, so neither the warning nor the flag applies:
        # flagging those rows would bury the real cases under the ~59% of the
        # catalogue that reports no eccentricity at all.
        if ecc > 0.0:
            geom_flags.append("omega_assumed_zero")
            if ecc >= phase_kepler.ECC_MIN:
                _warn_geom_omega_once(
                    pname,
                    f"{pname}: e = {ecc:.3f} but omega is "
                    f"unavailable; transit duration T14 assumes "
                    f"omega_p = 0 deg and is unreliable",
                )
        # omega_p = 0, i.e. omega_star = 180: e*sin(omega_star) = 0, so the
        # assumed angle leaves b and T14 at their e-averaged values.
        omega_star = 180.0
    else:
        omega_star = float(omega_star_raw)
    omega_planet = omega_star + 180.0                # phase_kepler convention
    omega_rad = np.radians(omega_star)

    # --- secondary eclipse phase & quadratures (exact Kepler) ---
    # The circular/eccentric split is a time tolerance, not a bare
    # eccentricity cut (see _ECC_TIMING_TOL_D above).  When the shift
    # matters and omega is unknown, no eclipse time can be trusted -- any
    # assumed omega can displace it by up to (4/pi)*e in phase -- so
    # both eclipse windows are suppressed (phi_sec = NaN) instead of being
    # built on a guess.  This only concerns the eclipse; the transit branch
    # below keeps its own omega_p = 0 assumption and warning untouched.
    if ecc_missing:
        geom_flags.append("ecc_assumed_zero")
    if ecc == 0.0:
        phi_sec = 0.5
        quad_pre_ph, quad_post_ph = 0.25, 0.75
    else:
        worst_shift_d = phase_kepler.max_eclipse_phase_shift(ecc) * P
        if worst_shift_d < _ECC_TIMING_TOL_D:
            geom_flags.append("ecc_negligible")
            phi_sec = 0.5
            quad_pre_ph, quad_post_ph = 0.25, 0.75
        elif not omega_known:
            _warn_geom_once(
                pname, "eclipse_omega_unknown",
                f"{pname}: e = {ecc:.3f} shifts the eclipse by up to "
                f"~{worst_shift_d * 1440.0:.0f} min but omega is "
                f"unavailable; pre/post-eclipse windows are suppressed "
                f"rather than built on an assumed omega_p = 0 deg",
            )
            phi_sec = np.nan
            quad_pre_ph = quad_post_ph = np.nan
        else:
            phi_sec = phase_kepler.secondary_eclipse_phase(ecc, omega_planet)
            quad_pre_ph, quad_post_ph = phase_kepler.quadrature_phases(
                ecc, omega_planet)

    # --- stellar / planetary radii ---
    st_rad = row.get("st_rad", np.nan)               # R_Sun
    pl_rade = row.get("pl_rade", np.nan)              # R_Earth
    st_mass = row.get("st_mass", np.nan)              # M_Sun

    # --- semi-major axis ---
    # compose_best_rows already rebuilds a missing or inconsistent a from
    # Kepler's 3rd law and names that as its donor; flag both routes.
    a_AU = row.get("pl_orbsmax", np.nan)
    field_sources = row.get("_field_sources")
    if pd.isna(a_AU):
        a_AU = _a_from_kepler(P, st_mass)
        if pd.notna(a_AU):
            geom_flags.append("a_from_kepler")
    elif (isinstance(field_sources, dict)
          and field_sources.get("pl_orbsmax") == "Kepler's 3rd law"):
        geom_flags.append("a_from_kepler")

    # --- light-travel delay across the orbit (Roemer delay) ---
    # Only needs a_AU, not the stellar radius, so it applies even on the
    # "missing Rs" fallback below.  ~40 s at a = 0.04 AU; reduces to 2a/c
    # for a circular orbit.  Quadratures need no such correction: the
    # planet is at the same line-of-sight distance as the star there, to
    # first order.
    if pd.notna(a_AU) and a_AU > 0 and np.isfinite(phi_sec):
        nu_tr = 0.5 * np.pi - omega_rad
        nu_occ = -0.5 * np.pi - omega_rad
        r_sum_over_a = (phase_kepler.orbital_radius_over_a(nu_tr, ecc)
                         + phase_kepler.orbital_radius_over_a(nu_occ, ecc))
        dt_ltt_d = a_AU * r_sum_over_a * _AU_LIGHT_S / 86400.0
        phi_sec += dt_ltt_d / P

    # If we still can't compute geometry, try pl_trandur as fallback
    if pd.isna(a_AU) or pd.isna(st_rad) or st_rad <= 0:
        trandur = row.get("pl_trandur", np.nan)      # hours from catalog
        if pd.notna(trandur) and trandur > 0:
            t14_h = trandur
            geom_flags.append("t14_from_trandur")
            _warn_geom_once(
                pname, "missing_a_or_rs_trandur",
                f"{pname}: semi-major axis or stellar radius unavailable; "
                f"using catalog pl_trandur={trandur:.3f} h for T14 instead "
                f"of Winn (2010)",
            )
        else:
            t14_h = 2.0
            geom_flags.append("t14_placeholder")
            _warn_geom_once(
                pname, "missing_a_or_rs_default",
                f"{pname}: semi-major axis or stellar radius unavailable "
                f"and no catalog pl_trandur; T14 assumed = 2.0 h "
                f"(placeholder, not a measurement)",
            )
        half_ph = (t14_h / 24.0) / (2.0 * P)
        return {
            "t14_h": t14_h, "t23_h": t14_h * 0.8,
            "half_ph": half_ph,
            "phi_sec": phi_sec,
            "t14_sec_h": t14_h,
            "half_ph_sec": half_ph,
            "b": 0.0, "ecc": ecc, "omega_star_deg": omega_star,
            "a_Rs": np.nan, "k": np.nan, "grazing": False,
            "b_occ": np.nan,
            "quad_pre_ph": quad_pre_ph, "quad_post_ph": quad_post_ph,
            "geom_flags": tuple(geom_flags),
        }

    a_Rs = a_AU / (st_rad * _R_SUN_AU)

    k = 0.01                                          # default Rp/R*
    if pd.notna(pl_rade) and pl_rade > 0:
        k = pl_rade * _R_EARTH_RSUN / st_rad
    else:
        geom_flags.append("k_assumed")

    # --- impact parameter ---
    incl = row.get("pl_orbincl", np.nan)
    if pd.isna(incl):
        b = 0.0
        cos_i = 0.0                                   # incl := 90 deg below
        incl = 90.0
        geom_flags.append("incl_assumed_90")
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

    # --- eccentricity correction (Eq. 16) ---
    # ecc_prim feeds T14/T23 (transit) and ecc_sec feeds T14_sec (eclipse)
    # below.  Neither depends on whether the composite geometry actually
    # transits, so compute both before the transit/no-transit branch.
    sqrt_1me2 = np.sqrt(1.0 - ecc ** 2) if ecc < 1 else 1.0
    ecc_prim = sqrt_1me2 / (1.0 + ecc * np.sin(omega_rad))
    ecc_sec = sqrt_1me2 / (1.0 - ecc * np.sin(omega_rad))

    # --- occultation impact parameter (Winn 2010 Eq. 8) ---
    # Distinct from the transit's `b` above whenever e*sin(omega_star) != 0;
    # reusing the transit `b` here misjudges t14_sec, by tens of per cent
    # for a near-grazing system.
    if ecc > 0:
        b_occ = a_Rs * cos_i * (1.0 - ecc ** 2) / (1.0 - ecc * np.sin(omega_rad))
    else:
        b_occ = a_Rs * cos_i

    # --- T14 (Eq. 14): does this composite geometry transit at all? ---
    # Mixing fields from different references (a, i, Rs, Rp each from
    # whichever reference reported them most recently) can produce an
    # impact parameter b > 1+k that no single reference ever measured --
    # i.e. Eq. 14 would need sqrt() of a negative number.  That is a sign
    # the *inputs* are inconsistent, not a valid grazing/non-transiting
    # planet, so it must not silently become a NaN that later passes every
    # comparison in match_events.
    if (1.0 + k) ** 2 - b ** 2 <= 0:
        trandur = row.get("pl_trandur", np.nan)
        if pd.notna(trandur) and trandur > 0:
            geom_flags.append("t14_from_trandur")
            _warn_geom_once(
                pname, "nontransiting_trandur",
                f"{pname}: composite geometry does not transit "
                f"(b={b:.3f} > 1+k={1.0 + k:.3f}); using catalog "
                f"pl_trandur={trandur:.3f} h for T14 instead of Winn (2010)",
            )
            t14_h = float(trandur)
            half_ph = (t14_h / 24.0) / (2.0 * P)
            return {
                "t14_h": t14_h, "t23_h": 0.0,
                "half_ph": half_ph,
                "phi_sec": phi_sec,
                "t14_sec_h": t14_h,
                "half_ph_sec": half_ph,
                "b": b, "ecc": ecc, "omega_star_deg": omega_star,
                "a_Rs": a_Rs, "k": k, "grazing": True,
                "b_occ": b_occ,
                "quad_pre_ph": quad_pre_ph, "quad_post_ph": quad_post_ph,
                "geom_flags": tuple(geom_flags),
            }
        _warn_geom_once(
            pname, "nontransiting_nan",
            f"{pname}: composite geometry does not transit "
            f"(b={b:.3f} > 1+k={1.0 + k:.3f}) and no catalog pl_trandur is "
            f"available; T14 left undefined (NaN) rather than assumed",
        )
        return {
            "t14_h": np.nan, "t23_h": np.nan,
            "half_ph": np.nan,
            "phi_sec": phi_sec,
            "t14_sec_h": np.nan,
            "half_ph_sec": np.nan,
            "b": b, "ecc": ecc, "omega_star_deg": omega_star,
            "a_Rs": a_Rs, "k": k, "grazing": True,
            "b_occ": b_occ,
            "quad_pre_ph": quad_pre_ph, "quad_post_ph": quad_post_ph,
            "geom_flags": tuple(geom_flags),
        }

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

    T14 = T14_circ * ecc_prim
    T23 = T23_circ * ecc_prim

    # --- phase half-widths ---
    half_ph = T14 / (2.0 * P)

    # --- eclipse duration (Eq. 14 with the occultation geometry) ---
    # A system can transit and still not be occulted, or vice versa,
    # whenever e*sin(omega_star) is sizeable -- unlike the transit check
    # above, b_occ > 1+k here is a real, common outcome, not a sign of
    # inconsistent inputs, so it must not fall back to pl_trandur (a
    # transit duration, not an eclipse one).
    if (1.0 + k) ** 2 - b_occ ** 2 <= 0:
        _warn_geom_once(
            pname, "nonocculting",
            f"{pname}: occultation geometry does not occur "
            f"(b_occ={b_occ:.3f} > 1+k={1.0 + k:.3f}); t14_sec left "
            f"undefined (NaN) rather than reused from the transit",
        )
        T14_sec = np.nan
        half_ph_sec = np.nan
        geom_flags.append("nonocculting")
    else:
        if (1.0 - k) ** 2 - b_occ ** 2 <= 0:
            # Grazing occultation: Winn's (2010) duration expressions assume
            # a chord centred on conjunction and crossed at constant speed,
            # which degrades for grazing, close-in eccentric orbits, so flag
            # t14_sec as approximate rather than pretend it is exact.
            geom_flags.append("b_occ_grazing")
        arg_sec = np.sqrt((1.0 + k) ** 2 - b_occ ** 2) / (a_Rs * sin_i)
        arg_sec = np.clip(arg_sec, -1.0, 1.0)
        T14_sec = (P / np.pi) * np.arcsin(arg_sec) * ecc_sec
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
        "b_occ": b_occ,
        "quad_pre_ph": quad_pre_ph, "quad_post_ph": quad_post_ph,
        "geom_flags": tuple(geom_flags),
    }


# ================================================================== #
#  5. EVENT PHASE WINDOWS                                             #
# ================================================================== #
def rv_orbit_shape(row, ecc_upper_limits_as_values=False):
    """
    ``(ecc, omega_p_deg)`` for the radial-velocity model of phase_kepler,
    which works with the planet's argument of periastron: the catalogue gives
    omega_star, so omega_p = omega_star + 180 deg.  ``None`` marks a value
    that is not available and lets ``phase_kepler.orbit_solution`` pick its
    branch (circular, or the envelope over every omega).

    An eccentricity known only as an upper limit counts as circular unless
    ``ecc_upper_limits_as_values`` is set.
    """
    ecc = row.get("pl_orbeccen")
    if pd.isna(ecc):
        return None, None
    if (limit_flag(row.get("pl_orbeccenlim")) == 1
            and not ecc_upper_limits_as_values):
        return None, None
    omega_star = row.get("pl_orblper")
    omega_p = ((float(omega_star) + 180.0) % 360.0
               if pd.notna(omega_star) else None)
    return float(ecc), omega_p


# Value fields whose NEA limit flag must be cleared when a CUSTOM_PLANETS
# entry overrides them: what the user types is a value, not a limit.
_LIMIT_FLAG_OF = {"pl_orbeccen": "pl_orbeccenlim", "pl_bmasse": "pl_bmasselim"}
_CUSTOM_MAG_MAP = {"st_jmag": "sy_jmag", "st_kmag": "sy_kmag"}


def merge_custom_planet(base, custom):
    """
    A CUSTOM_PLANETS entry overlaid on its catalogue row (``base``, a dict,
    or None for a target that is not in the filtered catalogue).  Every
    field the entry sets wins; the custom magnitudes are renamed to
    catalogue columns.  A mid-transit time typed by the user is BJD_TDB, so
    it does not inherit the time system of the catalogue row it replaces.
    """
    override = {_CUSTOM_MAG_MAP.get(k, k): v for k, v in custom.items()}
    row = {**base, **override} if base is not None else dict(override)
    for field, flag in _LIMIT_FLAG_OF.items():
        if field in override:
            row[flag] = 0
    if "pl_tranmid" in override and "pl_tsystemref" not in override:
        row["pl_tsystemref"] = "BJD-TDB"
    return row


def compute_event_windows(geom):
    """
    Phase windows for transit, pre-eclipse, post-eclipse.
    Phases in [0, 1).  Transit wraps around 0.

    The pre-/post-eclipse outer bounds are the exact orbital quadratures
    (``quad_pre_ph`` / ``quad_post_ph``, solved through Kepler's equation
    -- see ``phase_kepler.quadrature_phases``), not the fixed 0.25 / 0.75
    of a circular orbit.  For e = 0 the quadratures land exactly there, but
    for an eccentric orbit a fixed outer bound can produce an empty window
    on one side and an oversized one on the other (e.g. e = 0.3,
    omega_p = 0 makes the old fixed-0.25 pre-eclipse window empty).
    """
    half_ph = geom["half_ph"]
    phi_sec = geom["phi_sec"]
    half_ph_sec = geom["half_ph_sec"]
    quad_pre_ph = geom["quad_pre_ph"]
    quad_post_ph = geom["quad_post_ph"]

    windows = {
        "transit": [],
        "pre_eclipse": [],
        "post_eclipse": [],
    }

    # A non-finite half-width means the geometry could not be resolved (e.g.
    # a composite orbit that does not transit, see compute_transit_geometry).
    # Leaving the corresponding window empty means match_events sees "no
    # event" rather than a NaN interval that can spuriously match everything.
    if np.isfinite(half_ph):
        windows["transit"] = [(1.0 - half_ph, 1.0), (0.0, half_ph)]

    if (np.isfinite(phi_sec) and np.isfinite(half_ph_sec)
            and np.isfinite(quad_pre_ph) and np.isfinite(quad_post_ph)):
        pre_start = quad_pre_ph
        pre_end = phi_sec - half_ph_sec
        if pre_end > pre_start:
            windows["pre_eclipse"] = [(pre_start, pre_end)]

        post_start = phi_sec + half_ph_sec
        post_end = quad_post_ph
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
#  7. EVENT MATCHING: wrapped interval intersection                  #
# ================================================================== #
def _interval_width(intervals):
    """Sum of widths of non-wrapping intervals."""
    return sum(e - s for s, e in intervals)


def _unwrapped_phase(phases):
    """
    Orbital phase made continuous across the night grid: 0.98 followed by
    0.01 becomes 0.98, 1.01.  The integer part then counts the orbits
    started during the night.  Valid because a grid step is far shorter
    than half an orbit.
    """
    ph = np.asarray(phases, dtype=float)
    if ph.size == 0:
        return ph
    steps = (np.diff(ph) + 0.5) % 1.0 - 0.5
    return ph[0] + np.concatenate(([0.0], np.cumsum(steps)))


def _observable_stretches(cycles, obs_mask):
    """
    ``(start, end)`` in unwrapped phase of each contiguous observable stretch
    of the night.  The phases between two stretches -- e.g. a target near the
    pole that dips below the altitude limit around lower culmination -- never
    count as observable.
    """
    idx = np.where(obs_mask)[0]
    if len(idx) == 0:
        return []
    breaks = np.where(np.diff(idx) > 1)[0] + 1
    return [(float(cycles[st[0]]), float(cycles[st[-1]]))
            for st in np.split(idx, breaks)]


def _window_span(intervals):
    """
    One event window as a single ``(start, end)`` in orbital phase; the
    transit window ``[(1 - h, 1), (0, h)]`` becomes ``(-h, h)``.
    """
    if len(intervals) == 2 and intervals[0][1] == 1.0 and intervals[1][0] == 0.0:
        return intervals[0][0] - 1.0, intervals[1][1]
    if len(intervals) == 1:
        return intervals[0]
    raise ValueError(f"unexpected event window {intervals!r}")


def match_events(night, event_windows, event_constraints, geom):
    """
    For one observable night, check which events are schedulable.

    Each orbit is matched on its own: when the period is shorter than the
    night, the partial events of two consecutive orbits are two events, each
    with its own coverage, and never one event with their summed coverage.

    Returns list of event dicts.
    """
    if not night["has_obs"]:
        return []

    obs_mask = np.asarray(night["obs_mask"], dtype=bool)
    phases = np.asarray(night["phases"], dtype=float)
    cycles = _unwrapped_phase(phases)
    stretches = _observable_stretches(cycles, obs_mask)
    if not stretches:
        return []

    results = []
    for event_type, evt_intervals in event_windows.items():
        if not evt_intervals:
            continue

        lo, hi = _window_span(evt_intervals)
        evt_width = hi - lo
        # NaN interval bounds must reject the event, not silently pass every
        # comparison below (NaN comparisons are always False): a non-finite
        # width belongs to unresolved geometry that compute_event_windows
        # should already have filtered into an empty list, but this guards
        # against any other source of non-finite phase intervals too.
        if not np.isfinite(evt_width) or evt_width <= 0:
            continue

        min_cov = event_constraints.get(event_type, {}).get("min_coverage", 1.0)

        # Every orbit whose window reaches into the night grid, in phase
        # relative to that orbit, so that a window fully inside a stretch
        # gives a coverage of exactly 1.
        for k in range(int(np.floor(cycles[0] - hi)),
                       int(np.ceil(cycles[-1] - lo)) + 1):
            inter_width = sum(max(0.0, min(hi, s1 - k) - max(lo, s0 - k))
                              for s0, s1 in stretches)
            coverage = inter_width / evt_width
            if not np.isfinite(coverage) or coverage < min_cov:
                continue

            # UT times and altitude at midpoint of the intersection
            in_window = (cycles - k >= lo) & (cycles - k <= hi)
            idx_combined = np.where(obs_mask & in_window)[0]
            if len(idx_combined) == 0:
                continue
            idx_window = np.where(in_window)[0]

            i_start = idx_combined[0]
            i_end = idx_combined[-1]
            i_mid = idx_combined[len(idx_combined) // 2]

            results.append({
                "event_type": event_type,
                "coverage": float(coverage),
                "phase_start": float(phases[i_start]),
                "phase_end": float(phases[i_end]),
                "phase_mid": float(phases[i_mid]),
                "ut_start": night["times_utc"][i_start].iso,
                "ut_end": night["times_utc"][i_end].iso,
                "alt_at_midpoint": float(night["target_alt"][i_mid]),
                # Grid samples inside this orbit's window, observable or not,
                # for the plots (not saved to CSV).
                "_span": (int(idx_window[0]), int(idx_window[-1])),
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
        USE_ECC_UPPER_LIMITS,
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
    # table), used to gate PRESELECTION inclusion.
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
        print("  No planets to schedule; exiting.")
        return df, df_best, []

    show = ["pl_name", "pl_orbper", "pl_rade", "pl_tranmid", "ra", "dec"]
    show = [c for c in show if c in df_best.columns]
    print(df_best[show].to_string(index=False))

    # 2. Per planet: geometry + nights + events
    print("\n» [3/5] Scheduling planets")
    all_events = []

    # ── Inject CUSTOM_PLANETS from config ─────────────────────────
    # Custom planets are added after the filters and are not filtered
    # themselves.  When a custom entry shares its pl_name with a row of the
    # filtered catalog, that row is taken as the base and only the fields the
    # user explicitly listed in CUSTOM_PLANETS override it.  This keeps
    # catalog-derived parameters (st_mass, pl_orbincl, pl_orbsmax,
    # pl_orbeccen, …) intact, so downstream quantities like Kp still compute,
    # while still letting v_sys / mass / ephemeris be overridden per planet.
    # An entry for a planet the filters removed is scheduled from its own
    # fields alone.
    if CUSTOM_PLANETS:
        custom_names = {cp.get("pl_name") for cp in CUSTOM_PLANETS
                        if cp.get("pl_name")}
        catalog_by_name = {}
        if "pl_name" in df_best.columns:
            for _, r in df_best[df_best["pl_name"].isin(custom_names)].iterrows():
                catalog_by_name[r["pl_name"]] = r.to_dict()

        _rows = []
        n_merged = 0
        for cp in CUSTOM_PLANETS:
            base = catalog_by_name.get(cp.get("pl_name"))
            row = merge_custom_planet(base, cp)      # custom wins per field
            if base is not None:
                row["catalog_source"] = "custom+nea"
                n_merged += 1
            else:
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

    n_planets = len(df_best)
    for i_planet, (_, row) in enumerate(df_best.iterrows(), start=1):
        name = row["pl_name"]
        print(f"\n{'=' * 60}")
        print(f"  ● [{i_planet}/{n_planets}] {name}")
        print(f"{'=' * 60}")

        geom = compute_transit_geometry(
            row, ecc_upper_limits_as_values=USE_ECC_UPPER_LIMITS)
        print(f"  T14 = {geom['t14_h']:.2f} h  |  "
              f"phi_sec = {geom['phi_sec']:.4f}  |  "
              f"ecc = {geom['ecc']:.4f}")

        windows = compute_event_windows(geom)
        for etype, ints in windows.items():
            if ints:
                w = _interval_width(ints)
                print(f"  {etype:15s}: {ints}  (width={w:.5f})")
            elif etype == "transit" and not np.isfinite(geom.get("half_ph", np.nan)):
                print(f"  {etype:15s}: no window -- transit geometry unresolved "
                      f"(t14_h is not finite)")

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

        # Systemic velocity for the telluric page and the card: user value,
        # then the archive's st_radv, then Gaia DR3 / SIMBAD.  None when no
        # source has it, in which case the telluric page is skipped.
        vsys = resolve_systemic_velocity(row)
        if vsys is not None and vsys[2] not in ("user", "NEA"):
            print(f"  v_sys = {vsys[0]:+.2f} ± {vsys[1]:.2f} km/s from "
                  f"{vsys[2]} (none in the archive)")

        try:
            summary_path = render_planet_summary(row, metrics, planet_dir,
                                                 geom=geom, vsys=vsys)
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

        v_sys_kms = vsys[0] if vsys is not None else None

        # Planet RV semi-amplitude Kp: needed for the telluric plot's
        # planet-RV band. Falls back to None if period / st_mass / mass missing.
        try:
            kp_kms = compute_kp(row, tsm_row)
        except Exception as exc:
            print(f"  ⚠  Kp compute failed for {name}: {exc}")
            kp_kms = None

        # Orbit shape for the planetary RV trace.  Kept as None when the
        # catalogue does not give them, so that phase_kepler can pick the
        # circular / Keplerian / omega-envelope branch explicitly instead of
        # silently defaulting.  omega_p = catalogue omega_star + 180 deg.
        ecc_rv, omega_p_rv = rv_orbit_shape(
            row, ecc_upper_limits_as_values=USE_ECC_UPPER_LIMITS)

        target = {
            "name": name,
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "period": float(row["pl_orbper"]),
            "t0_bjd": t0_bjd,
            "v_sys_kms": v_sys_kms,
            "v_sys_source": vsys[2] if vsys is not None else None,
            "kp_kms": kp_kms,
            "ecc": ecc_rv,
            "omega_p_deg": omega_p_rv,
            "ecc_upper_limit": (ecc_rv is not None and limit_flag(
                row.get("pl_orbeccenlim")) == 1),
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
                e["geom_flags"] = "|".join(geom["geom_flags"])
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

    n_to_plot = len(grouped)
    for i_plot, (planet_name, planet_events) in enumerate(grouped.items(), 1):
        planet_dir = planet_events[0]["_planet_dir"]
        obs_label = OBSERVATORY["name"].replace(" ", "_")
        print(f"\n  ● [{i_plot}/{n_to_plot}] {planet_name}")

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
