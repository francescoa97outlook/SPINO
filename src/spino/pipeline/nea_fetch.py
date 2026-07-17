"""
NEA Catalog Fetch
=================
Optional online fetch of the NASA Exoplanet Archive PS table via its TAP
service.  On any failure (network error, timeout, HTTP error) the caller
should fall back to a local CSV (see ``resolve_catalog_path``).

The column allow-list ``NEA_COLUMNS`` lists exactly the columns the phase
scheduler pipeline reads (plus a few extra magnitudes useful for GIANO-B
target selection).  Restricting the SELECT keeps the cached CSV small and
makes the dependency between the pipeline and the catalog explicit.
"""
from __future__ import annotations

from pathlib import Path

import requests

NEA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

NEA_COLUMNS = [
    # identification & meta
    "pl_name", "hostname", "pl_refname", "pl_pubdate",
    "soltype", "pl_controv_flag", "default_flag",
    "discoverymethod", "disc_year", "disc_telescope", "disc_facility",
    # coordinates
    "ra", "dec",
    # orbit
    "pl_orbper", "pl_orbpererr1", "pl_orbpererr2",
    "pl_orbsmax", "pl_orbsmaxerr1", "pl_orbsmaxerr2",
    "pl_orbeccen", "pl_orblper", "pl_orbincl", "pl_imppar",
    # planet
    "pl_rade", "pl_radeerr1", "pl_radeerr2",
    "pl_bmasse", "pl_bmasseerr1", "pl_bmasseerr2",
    "pl_masse", "pl_msinie", "pl_dens", "pl_insol",
    "pl_eqt", "pl_tranmid", "pl_tranmiderr1", "pl_tranmiderr2",
    "pl_tsystemref", "pl_trandur", "pl_rvamp",
    # star
    "st_teff", "st_rad", "st_mass", "st_met",
    "st_radv", "st_spectype",
    # system magnitudes
    "sy_jmag", "sy_hmag", "sy_kmag", "sy_vmag", "sy_gaiamag",
]


def fetch_nea_catalog(out_path: str, source: str = "NEA",
                     timeout: float = 30) -> str:
    """
    Query the NEA TAP service for ``NEA_COLUMNS`` from the ``ps`` table,
    keeping only ``Published Confirmed`` rows.  ``source`` controls the
    WHERE clause:

      "NEA":  no extra filter (full PS confirmed)
      "TESS": adds ``AND disc_facility LIKE '%TESS%'``
      "BOTH": same as NEA (per-row source is derived downstream)

    Writes the response CSV atomically to ``out_path``.

    Raises any underlying ``requests`` / IO exception; the caller is
    responsible for catching and falling back.
    """
    if source not in ("NEA", "TESS", "BOTH"):
        raise ValueError(
            f"source must be one of NEA/TESS/BOTH, got {source!r}"
        )

    where = "soltype LIKE 'Published Confirmed'"
    if source == "TESS":
        where += " AND disc_facility LIKE '%TESS%'"

    query = (
        f"SELECT {','.join(NEA_COLUMNS)} "
        f"FROM ps "
        f"WHERE {where}"
    )
    resp = requests.get(
        NEA_TAP_URL,
        params={"query": query, "format": "csv"},
        timeout=timeout,
    )
    resp.raise_for_status()

    text = resp.text
    if not text or "," not in text.splitlines()[0]:
        raise RuntimeError(
            f"NEA TAP returned an unexpected response "
            f"(first line: {text.splitlines()[0][:120] if text else '<empty>'!r})"
        )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    return str(out)


def resolve_catalog_path(
    source: str,
    online: bool,
    catalog_dir: str,
    timeout: float = 30,
) -> str:
    """
    Decide which CSV path the pipeline should load for ``source``.

    The filename is always ``PS_latest_{source}.csv`` inside
    ``catalog_dir``.  If ``online`` is True, attempt a fresh fetch into
    that file and return its path on success.  On any failure print a
    single warning line and return the same path (the caller will load
    the local copy if it exists, or raise on read).  If ``online`` is
    False, return the path directly without fetching.
    """
    if source not in ("NEA", "TESS", "BOTH"):
        raise ValueError(
            f"source must be one of NEA/TESS/BOTH, got {source!r}"
        )

    out_path = str(Path(catalog_dir) / f"PS_latest_{source}.csv")

    if online:
        try:
            print(
                f"Fetching NEA catalog online (source={source}, "
                f"{len(NEA_COLUMNS)} columns)..."
            )
            fetch_nea_catalog(out_path, source=source, timeout=timeout)
            print(f"  ✔  saved → {out_path}")
        except Exception as e:  # noqa: BLE001  (any failure falls back)
            print(
                f"  ⚠  online fetch failed ({e!s}); "
                f"falling back to local CSV: {out_path}"
            )

    return out_path
