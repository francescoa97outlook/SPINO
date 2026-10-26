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
| `USE_ECC_UPPER_LIMITS` | bool | Eccentricities archived only as upper limits (e.g. `e < 0.058`) are treated as circular and flagged `ecc_upper_limit` (default `false`). Set `true` to use the limit as the eccentricity, a worst case in which, without an argument of periastron from the same reference, the eclipse windows are suppressed and the planetary radial velocity becomes an envelope over every ω. |

### How the catalogue is read

The NASA Exoplanet Archive lists one row per published solution. SPINO composes
one row per planet: the ephemeris from the most precise solution, every other
field from the most recent reference that reports it, with two exceptions.

- Eccentricity and argument of periastron are fitted together, so both come from
  the most recent reference that reports an eccentricity; ω is never borrowed
  from a different solution. Eccentricities given only as lower limits are not
  used.
- A measured planetary mass is preferred to a more recent limit; an upper limit
  is used only when nothing better exists, and is shown as `< M` on the summary
  card, together with the TSM computed from it as a lower limit.

The argument of periastron `pl_orblper` is read as published, which for the
radial-velocity solutions it comes from is ω★, that of the star's reflex orbit:
the transit falls at true anomaly π/2 − ω★ (Winn 2010), the convention also
assumed by the archive's own Transit and Ephemeris Service. A reference that
quotes the planet's ω instead would place the eclipse at the mirror phase.

The mid-transit time `pl_tranmid` is brought to BJD_TDB before it is
propagated, according to the time system that the archive records in
`pl_tsystemref`:

- `BJD`, `BJD-TDB` and `BJD-TT` are used as they are (TT and TDB differ by less
  than 2 ms);
- `BJD-UTC` gains TDB − UTC (69.184 s since 2017), `BJD-TCB` is brought from
  TCB to TDB;
- `HJD` (UTC) and `HJD-TDB` are moved from the Sun to the barycentre, and the
  former also from UTC to TDB;
- a bare `JD` is used as it is: the archive applies that label to many epochs
  that are already BJD_TDB, which agree with the BJD-TDB rows of the same
  planet as published and disagree by minutes once read as geocentric UTC.
  Only an explicit `JD-UTC` is converted from geocentric UTC.

## Filters

| Key | Type | Meaning |
|---|---|---|
| `DESERT_FILTER` | `"all"` \| `"desert"` \| `"nondesert"` | Keep planets inside / outside the Neptunian-desert polygon, or all. |
| `EXTRA_FILTERS` | list of dict | Sequential AND filters. Each dict is `{"column": name, "min": x, "max": y}` or `{"column": name, "contains": text}`. |

## Observatory

The Observatory tab starts with a **preset** picker (CRIRES+, IGRINS-2, GIANO-B,
and `New`). Selecting a built-in preset auto-fills every field below with that
telescope/instrument's site data; `New` lets you type your own values (editing any
field switches the picker to `New`). The preset is a GUI convenience only: what is
saved is the resulting `OBSERVATORY` dict.

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
| `CONSTRAINTS` | dict | `min_target_alt` (deg) and `max_sun_alt` (deg; −6, −12 and −18 are civil, nautical and astronomical twilight): a grid sample is observable when the target is above the first and the Sun below the second. `moon_dist_factor` is the factor f of the Moon rule, see below. |
| `EVENT_CONSTRAINTS` | dict | `transit` / `pre_eclipse` / `post_eclipse`, each `{"min_coverage": 0..1}`, the fraction of the event window that must be observable. Each orbit is matched on its own: on a period shorter than the night, the partial events of two consecutive orbits are two events, each with its own coverage. |
| `TIME_RESOLUTION_MIN` | int (min) | Grid step for the night-by-night sampling. |
| `PRESELECTION_MIN_YEAR` | int | Only planets whose oldest reference year exceeds this are listed in `preselection.csv`. |

### The Moon rule

For each night SPINO measures, at local midnight, the Moon–target distance and
the illuminated fraction k of the lunar disc. The rule asks the distance to
exceed f × k × 100°, or the Moon to be below the horizon. Its result is
reported, never applied: it appears in the footer of the night plot (`OK` or
`TOO CLOSE`, `rule off` when f = 0, the default), in the calendar (bar colour
for k, red edge when the rule fails) and in the `moon_illum`, `moon_sep` and
`moon_ok` columns of `events_summary.csv`. No event is removed because of the
Moon.

## Custom planets

`CUSTOM_PLANETS` is a list of dicts injected in addition to the filtered
catalog. Recognised fields (all optional except `pl_name`):

`pl_name`, `pl_orbper` (d), `pl_rade` (R⊕), `pl_bmasse` (M⊕), `pl_eqt` (K),
`st_teff` (K), `st_mass` (M☉), `st_rad` (R☉), `st_jmag`, `st_kmag`, `ra` (deg),
`dec` (deg), `pl_tranmid` (BJD_TDB), `pl_orbsmax` (AU), `pl_orbeccen`,
`pl_orblper` (deg), `v_sys` (km/s).

Custom planets are added after the filters and are not filtered themselves. For
a target that passes the filters, any field you supply here overrides the value
of its composed catalogue row while the rest are kept; a target that the filters
remove is scheduled from the fields you give alone. The filters of a run should
therefore admit the planets entered here. A `pl_tranmid` typed here is read as
BJD_TDB and does not inherit the time system of the catalogue row.

### Orbit shape

`pl_orbeccen` and `pl_orblper` drive the planetary radial-velocity trace on the
telluric-overlap plot, and both accept `null` (or may be omitted entirely).
`pl_orblper` is ω★, the argument of periastron of the star's reflex orbit, as
in the archive and in radial-velocity papers (the planet's is ω★ + 180°). A
value typed here is always taken as a measurement, never as a limit.

- `pl_orbeccen` null, omitted, or below 0.01 means a circular orbit, with the
  trace `Kp·sin(2πφ)`. Below that threshold the eccentric and circular traces
  are indistinguishable at any realistic spectral resolution.
- With a non-negligible eccentricity and `pl_orblper` given, the trace is the
  full Keplerian solution, and the circular approximation is drawn alongside it
  so the difference is visible.
- With a non-negligible eccentricity and `pl_orblper` null or omitted, there is
  no preferred trace: the plot shows the envelope spanned by every possible
  argument of periastron, and the transit geometry (`T14`, `phi_sec`) is
  flagged as unreliable in the run log, since it too depends on this angle.

An eccentricity outside `[0, 1)` is rejected with a warning and the orbit falls
back to circular.

## Telluric position plot

| Key | Type | Meaning |
|---|---|---|
| `SKY_TRANSMISSION_FITS` | path or `""` | Sky-transmission FITS for the telluric-overlap page; empty string disables that page. |
| `TELLURIC_LAMBDA_RANGE_NM` | `[start, stop]` (nm) | Wavelength slice displayed. |
| `TELLURIC_RV_GRID_KMS` | `[start, stop, step]` (km/s) | Radial-velocity grid of the telluric autocorrelation, in whole steps from `start` and never beyond `stop`. The default `[-50, 50, 1]` has 101 points, 0 included. |
| `TELLURIC_PAD_HOURS` | float (h) | Padding either side of the synthetic window. |
| `TELLURIC_EXP_TIME_S` | float (s) | Synthetic exposure cadence. |

> The bundled FITS is an ESO SkyCalc model of the atmospheric transmission above
> Cerro Paranal (Noll et al. 2012; Jones et al. 2013), computed at R = 100 000 for
> 3.5 mm of precipitable water vapour and airmass 1.15 over 0.94–2.44 µm, with
> default wavelength/RV settings tuned to one GIANO-B order. If you point the scheduler at a different
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
