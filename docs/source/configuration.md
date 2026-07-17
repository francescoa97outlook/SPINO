# Configuration reference

Every parameter below is a global in
`src/spino/pipeline/phase_config.py` and an editable field in the
GUI. The runner overlays the GUI/JSON values onto that module before running the
pipeline, so the JSON key names must match these names exactly.

## Catalog

| Key | Type | Meaning |
|---|---|---|
| `CATALOG_SOURCE` | `"NEA"` \| `"TESS"` \| `"BOTH"` | Which cached NASA Exoplanet Archive subset to load. |
| `FETCH_NEA_ONLINE` | bool | Try the NASA TAP service first, falling back to the local CSV on any failure. |
| `NEA_FETCH_TIMEOUT` | int (s) | Timeout for the online TAP request. |
| `CATALOG_DIR` | path | Directory holding the `PS_latest_{source}.csv` cache files. |

## Filters

| Key | Type | Meaning |
|---|---|---|
| `DESERT_FILTER` | `"all"` \| `"desert"` \| `"nondesert"` | Keep planets inside / outside the Neptunian-desert polygon, or all. |
| `EXTRA_FILTERS` | list of dict | Sequential AND filters. Each dict is `{"column": name, "min": x, "max": y}` or `{"column": name, "contains": text}`. |

## Observatory

`OBSERVATORY` is a dict with:

| Field | Type | Meaning |
|---|---|---|
| `name` | str | Short label used in output filenames. |
| `telescope` | str | Telescope name (documentation only). |
| `instrument` | str | Instrument name (documentation only). |
| `lat` | float (deg, +N) | Latitude. |
| `lon` | float (deg, +E) | Longitude. |
| `alt` | float (m) | Altitude. |
| `timezone` | str | IANA timezone name (e.g. `America/Santiago`). |

## Time & constraints

| Key | Type | Meaning |
|---|---|---|
| `DATE_RANGE` | dict | `{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}` proposal window. |
| `CONSTRAINTS` | dict | `min_target_alt` (deg), `max_sun_alt` (deg; −10 = NEA twilight, −18 = astronomical night), `moon_dist_factor` (0 disables). |
| `EVENT_CONSTRAINTS` | dict | `transit` / `pre_eclipse` / `post_eclipse`, each `{"min_coverage": 0..1}`, the fraction of the event window that must be observable. |
| `TIME_RESOLUTION_MIN` | int (min) | Grid step for the night-by-night sampling. |
| `PRESELECTION_MIN_YEAR` | int | Only planets whose oldest reference year exceeds this are listed in `preselection.csv`. |

## Custom planets

`CUSTOM_PLANETS` is a list of dicts injected in addition to the filtered
catalog. Recognised fields (all optional except `pl_name`):

`pl_name`, `pl_orbper` (d), `pl_rade` (R⊕), `pl_bmasse` (M⊕), `pl_eqt` (K),
`st_teff` (K), `st_mass` (M☉), `st_rad` (R☉), `st_jmag`, `st_kmag`, `ra` (deg),
`dec` (deg), `pl_tranmid` (BJD), `pl_orbsmax` (AU), `pl_orbeccen`, `v_sys` (km/s).

For a target already in the catalog, any field you supply here overrides the
catalog value while the rest are kept.

## Telluric position plot

| Key | Type | Meaning |
|---|---|---|
| `SKY_TRANSMISSION_FITS` | path or `""` | Sky-transmission FITS for the telluric-overlap page; empty string disables that page. |
| `TELLURIC_LAMBDA_RANGE_NM` | `[start, stop]` (nm) | Wavelength slice displayed. |
| `TELLURIC_RV_GRID_KMS` | `[start, stop, step]` (km/s) | Radial-velocity grid. |
| `TELLURIC_PAD_HOURS` | float (h) | Padding either side of the synthetic window. |
| `TELLURIC_EXP_TIME_S` | float (s) | Synthetic exposure cadence. |

> The bundled FITS is a GIANO-B sky-transmission spectrum with default
> wavelength/RV settings tuned for it. If you point the scheduler at a different
> instrument, update the FITS **and** the wavelength/RV settings accordingly, or
> clear `SKY_TRANSMISSION_FITS` to skip the telluric page.

## Output & plot

| Key | Type | Meaning |
|---|---|---|
| `OUTPUT_DIR` | path | Root for all generated PDFs / CSVs. Defaults to `./phase_scheduler_output`. |
| `AUX_DIR` | path | Folder with `desert_boundaries.txt` and the KDE npz. |
| `DESERT_BOUNDARY_FILE` | path | Castro-González (2024) desert polygon. |
| `KDE_FILE` | path | KDE background density for the period–radius landscape. |
| `P_MAX` | int (d) | Landscape x-axis (period) upper limit. |
| `R_MAX` | int (R⊕) | Landscape y-axis (radius) upper limit. |
