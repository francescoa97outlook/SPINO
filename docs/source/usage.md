# Usage

Launch the app:

```bash
spino        # or: python -m spino
```

The window is a set of tabs (one per configuration group) plus a **Run** tab.
Every field is pre-filled with the bundled defaults. The blue **?** button on
each tab opens a help popup describing that tab's parameters.

## Tabs

| Tab | What you set |
|---|---|
| **Catalog** | Which NASA Exoplanet Archive subset to load (`NEA` / `TESS` / `BOTH`), whether to fetch online, timeout, and the catalog cache directory. |
| **Filters** | The desert filter (`all` / `desert` / `nondesert`) and an editable **EXTRA_FILTERS** table: add rows of `column` + `min`/`max` (or `contains`); they are applied in sequence (logical AND). |
| **Observatory** | A preset picker (CRIRES+, IGRINS-2, GIANO-B, or `New`) that auto-fills the fields, then site name (used in output filenames), telescope, instrument, latitude, longitude, altitude, and timezone. |
| **Constraints** | Proposal window (start/end), observing constraints (min target altitude, max Sun altitude, moon distance), per-event coverage fractions, time resolution, and preselection year. |
| **Custom Planets** | A JSON list of hand-entered targets injected in addition to the filtered catalog. Use **Insert example** to add a template, **Validate JSON** to check it. |
| **Telluric** | The sky-transmission FITS (leave blank to disable the telluric page), the wavelength slice, RV grid, and synthetic-window parameters. |
| **Output & Plot** | Output directory, desert-landscape aux files, and landscape axis limits. |

## Running

Open the **Run** tab and press **▶ Run**. The app:

1. if `OUTPUT_DIR` already contains results, asks whether to delete them and run a
   fresh search; choosing **No** cancels the run and keeps the old results,
2. collects every field into a `settings.json` (written inside `OUTPUT_DIR`),
3. launches the pipeline in a background subprocess,
4. streams its log into the dark log pane (press **■ Stop** to terminate),
5. when it finishes, lists the generated `*.pdf` / `*.csv` under **Generated
   files**. **Double-click** any of them to open it in your system viewer.

Because each confirmed run starts from an empty `OUTPUT_DIR`, stale folders from a
previous search (planets no longer selected) never linger.

## Presets

- **Save preset**: writes the current form values to a JSON file you choose.
- **Load preset**: repopulates every field from a JSON file.
- **Reset defaults**: restores the bundled defaults.

Preset JSON files use the same `{GLOBAL_NAME: value}` schema as the
`settings.json` consumed by the runner, so they are interchangeable.

## Outputs

For each scheduled planet, inside `OUTPUT_DIR/<planet>[_TSM][_ESM]/`:

- `<planet>_summary.pdf`: one-page parameter card with TSM/ESM bars,
- `events_summary.csv`: the per-planet event table,
- `calendar_<event>.pdf`: night-by-night calendars (per event type present),
- `transit.pdf`, `pre_eclipse.pdf`, `post_eclipse.pdf`: one plot page per
  event (altitude vs. time, plus a telluric-overlap page when enabled).

At the `OUTPUT_DIR` root: `PR_landscape.pdf` (the period-radius desert map) and
`preselection.csv`, a table listing the qualifying planets (recent references with
TSM or ESM above threshold) with their key properties.

## Headless run

The Run tab is a thin wrapper around:

```bash
python -m spino.runner settings.json
```

Run that directly for scripted / batch use. A minimal single-target
`settings.json` needs at least an `OUTPUT_DIR`, a `DATE_RANGE`, an
`OBSERVATORY`, and either catalog filters or a `CUSTOM_PLANETS` entry; any key
you omit falls back to the pipeline default.
