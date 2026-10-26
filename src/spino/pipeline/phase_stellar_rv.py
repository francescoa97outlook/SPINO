"""
Systemic velocity of the host star
==================================
The telluric-overlap page needs the systemic velocity of the host to place
the planet in the Earth frame.  It is taken, in order, from the user
(CUSTOM_PLANETS ``v_sys``), from the archive (``st_radv``), and otherwise
from whichever of Gaia DR3 and SIMBAD quotes the smaller uncertainty:

* Gaia DR3 ``radial_velocity`` (Katz et al. 2023), read from the Gaia archive
  for the DR3 source that SIMBAD lists among the identifiers of the host;
* the radial velocity that SIMBAD adopts for the host, with its bibcode.

Both lookups need the network.  They are skipped quietly when it is not
available, cached per host, and their source travels with the value.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import requests

GAIA_TAP_URL = "https://gea.esac.esa.int/tap-server/tap/sync"
LOOKUP_TIMEOUT_S = 30

_cache: dict[str, tuple | None] = {}


# ------------------------------------------------------------------ #
#  Parsers (pure, tested on the real response formats)                #
# ------------------------------------------------------------------ #
def parse_gaia_rv_csv(text: str):
    """``(rv, err)`` [km/s] from a Gaia TAP CSV answer, or None."""
    table = pd.read_csv(io.StringIO(text))
    if table.empty:
        return None
    rv = table["radial_velocity"].iloc[0]
    err = table["radial_velocity_error"].iloc[0]
    if pd.isna(rv):
        return None
    return float(rv), float(err) if pd.notna(err) else np.nan


def gaia_dr3_id(identifiers):
    """Gaia DR3 source_id among a star's SIMBAD identifiers, or None."""
    for ident in identifiers:
        text = str(ident).strip()
        if text.startswith("Gaia DR3 "):
            return int(text.split()[-1])
    return None


def parse_simbad_rv(table):
    """``(rv, err, bibcode)`` [km/s] from a SIMBAD query_object table."""
    if table is None or len(table) == 0 or "rvz_radvel" not in table.colnames:
        return None
    rv = table["rvz_radvel"][0]
    if np.ma.is_masked(rv) or not np.isfinite(rv):
        return None
    err = table["rvz_err"][0] if "rvz_err" in table.colnames else np.nan
    err = np.nan if np.ma.is_masked(err) else float(err)
    bib = str(table["rvz_bibcode"][0]) if "rvz_bibcode" in table.colnames else ""
    return float(rv), err, bib


# ------------------------------------------------------------------ #
#  Network lookups                                                    #
# ------------------------------------------------------------------ #
def gaia_lookup(host: str):
    """Gaia DR3 radial velocity of ``host`` via its SIMBAD identifiers."""
    from astroquery.simbad import Simbad

    ids = Simbad.query_objectids(host)
    if ids is None or len(ids) == 0:
        return None
    source_id = gaia_dr3_id(ids[ids.colnames[0]])
    if source_id is None:
        return None
    query = ("SELECT source_id, radial_velocity, radial_velocity_error "
             f"FROM gaiadr3.gaia_source WHERE source_id = {source_id}")
    resp = requests.post(GAIA_TAP_URL, timeout=LOOKUP_TIMEOUT_S, data={
        "REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query})
    resp.raise_for_status()
    return parse_gaia_rv_csv(resp.text)


def simbad_lookup(host: str):
    """Radial velocity adopted by SIMBAD for ``host``, with its bibcode."""
    from astroquery.simbad import Simbad

    s = Simbad()
    s.add_votable_fields("rvz_radvel", "rvz_err", "rvz_bibcode")
    return parse_simbad_rv(s.query_object(host))


# ------------------------------------------------------------------ #
#  Resolution                                                         #
# ------------------------------------------------------------------ #
def _finite(x) -> bool:
    try:
        return x is not None and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def resolve_systemic_velocity(row, gaia=gaia_lookup, simbad=simbad_lookup):
    """
    ``(v_sys, err, source)`` [km/s] for the host of ``row``, or None.

    ``source`` is "user", "NEA", "Gaia DR3" or "SIMBAD (<bibcode>)"; the
    archive and user values carry no uncertainty here.  Between Gaia DR3 and
    SIMBAD the smaller quoted uncertainty wins, a value without one ranking
    last.  A lookup that fails (no network, unknown host) is skipped.
    """
    user = row.get("v_sys")
    if _finite(user):
        return float(user), None, "user"
    nea = row.get("st_radv")
    if _finite(nea):
        return float(nea), None, "NEA"

    host = str(row.get("hostname") or row.get("pl_name") or "").strip()
    if not host:
        return None
    use_cache = gaia is gaia_lookup and simbad is simbad_lookup
    if use_cache and host in _cache:
        return _cache[host]
    best = _best_lookup(host, gaia, simbad)
    if use_cache:
        _cache[host] = best
    return best


def host_name_candidates(host: str) -> list[str]:
    """
    Names to try for ``host``: the archive's own, then, for a primary
    component ("TOI-2587 A"), the system name, which SIMBAD resolves to the
    primary when it does not know the component.  Other components are not
    stripped, since the system name would then return a different star.
    """
    names = [host]
    if host.endswith(" A") and len(host) > 2:
        names.append(host[:-2].rstrip())
    return names


def _best_lookup(host, gaia, simbad):
    """The result with the smallest quoted uncertainty for the first name of
    ``host_name_candidates`` that either service knows, or None."""
    for name in host_name_candidates(host):
        found = []
        try:
            g = gaia(name)
            if g is not None:
                found.append((g[0], g[1], "Gaia DR3"))
        except Exception as exc:      # noqa: BLE001 (network or service error)
            print(f"      × Gaia DR3 RV lookup failed for {name!r}: {exc}")
        try:
            s = simbad(name)
            if s is not None:
                found.append((s[0], s[1], f"SIMBAD ({s[2]})" if s[2] else "SIMBAD"))
        except Exception as exc:      # noqa: BLE001
            print(f"      × SIMBAD RV lookup failed for {name!r}: {exc}")
        if found:
            found.sort(key=lambda f: f[1] if _finite(f[1]) else np.inf)
            return found[0]
    return None
