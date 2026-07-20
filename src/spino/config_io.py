"""
config_io: bridge between the GUI widgets and the pipeline configuration.

The pipeline is driven entirely by the module-level globals in
``pipeline/phase_config.py``.  This module:

* reads those globals to obtain the **default** value of every parameter
  (so the GUI never hard-codes defaults that could drift from the pipeline);
* describes each parameter's *group*, *kind* and help text (consumed by the
  panels and the ``HelpButton`` popups);
* serialises a flat ``{GLOBAL_NAME: value}`` settings dict to / from JSON.

The subprocess entry point ``runner.py`` loads that JSON, ``setattr``s every
key onto ``phase_config`` and then runs the pipeline, so the set of keys here
must match the global names in ``phase_config.py`` exactly.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
#  Paths
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.join(_HERE, "pipeline")
DATA_DIR = os.path.join(_HERE, "data")


def _import_phase_config():
    """Import the pipeline's ``phase_config`` (flat import) in isolation.

    ``phase_config`` only depends on the stdlib ``os`` module, so importing it
    here is cheap and does not drag in numpy/astropy/matplotlib.
    """
    if PIPELINE_DIR not in sys.path:
        sys.path.insert(0, PIPELINE_DIR)
    import phase_config  # noqa: E402  (path set up above)
    return phase_config


# --------------------------------------------------------------------------- #
#  The list of config globals the GUI exposes (order defines nothing;
#  the panels decide layout).  Every name here must exist in phase_config.
# --------------------------------------------------------------------------- #
CONFIG_KEYS: List[str] = [
    # catalog
    "CATALOG_SOURCE", "FETCH_NEA_ONLINE", "NEA_FETCH_TIMEOUT", "CATALOG_DIR",
    # filters
    "DESERT_FILTER", "EXTRA_FILTERS",
    # observatory
    "OBSERVATORY",
    # time & constraints
    "DATE_RANGE", "CONSTRAINTS", "EVENT_CONSTRAINTS",
    "TIME_RESOLUTION_MIN", "PRESELECTION_MIN_YEAR",
    # custom planets
    "CUSTOM_PLANETS",
    # telluric
    "SKY_TRANSMISSION_FITS", "TELLURIC_LAMBDA_RANGE_NM", "TELLURIC_RV_GRID_KMS",
    "TELLURIC_PAD_HOURS", "TELLURIC_EXP_TIME_S",
    # output & plot
    "OUTPUT_DIR", "AUX_DIR", "DESERT_BOUNDARY_FILE", "KDE_FILE", "P_MAX", "R_MAX",
]

# Enumerated choices used by dropdowns.
CATALOG_SOURCES = ["NEA", "TESS", "BOTH"]
DESERT_FILTERS = ["all", "desert", "nondesert"]

# Columns offered in the EXTRA_FILTERS row editor (NASA-Archive style names).
FILTER_COLUMNS = [
    "pl_orbper", "pl_rade", "pl_bmasse", "pl_eqt", "pl_dens",
    "st_teff", "st_rad", "st_mass", "sy_jmag", "sy_kmag",
    "ra", "dec", "pl_orbsmax", "pl_orbeccen", "disc_year",
]

# Ordered numeric fields of a CUSTOM_PLANETS entry (besides pl_name).
CUSTOM_PLANET_FIELDS = [
    "pl_orbper", "pl_rade", "pl_bmasse", "pl_eqt", "st_teff", "st_mass",
    "st_rad", "st_jmag", "st_kmag", "ra", "dec", "pl_tranmid",
    "pl_orbsmax", "pl_orbeccen", "pl_orblper", "v_sys",
]

TIMEZONES = [
    "UTC", "Atlantic/Canary", "America/Santiago", "Pacific/Honolulu",
    "Europe/Rome", "Europe/London", "America/New_York", "Australia/Sydney",
]

# --------------------------------------------------------------------------- #
#  Built-in observatory / instrument presets for the Observatory tab dropdown.
#  Selecting a preset auto-fills every OBSERVATORY field; the extra "New" entry
#  lets the user type their own values in the same fields.
# --------------------------------------------------------------------------- #
OBSERVATORY_PRESET_NEW = "New"
OBSERVATORY_PRESETS: Dict[str, Dict[str, Any]] = {
    "CRIRES+": {
        "name": "VLT",
        "telescope": "VLT UT3 (Melipal)",
        "instrument": "CRIRES+",
        "lat": -24.6275,
        "lon": -70.4044,
        "alt": 2635,
        "timezone": "America/Santiago",
    },
    "IGRINS-2": {
        "name": "Gemini North",
        "telescope": "Gemini North",
        "instrument": "IGRINS-2",
        "lat": 19.8238,
        "lon": -155.4691,
        "alt": 4213,
        "timezone": "Pacific/Honolulu",
    },
    "GIANO-B": {
        "name": "TNG",
        "telescope": "TNG",
        "instrument": "GIANO-B",
        "lat": 28.7569,
        "lon": -17.8850,
        "alt": 2387,
        "timezone": "Atlantic/Canary",
    },
}

# --------------------------------------------------------------------------- #
#  Help text (parameter -> one-line description) for the HelpButton popups.
# --------------------------------------------------------------------------- #
HELP: Dict[str, Dict[str, str]] = {
    "Catalog": {
        "CATALOG_SOURCE": "Which cached NASA Exoplanet Archive subset to load: "
                          "NEA (all confirmed), TESS (TESS-discovered), or BOTH.",
        "FETCH_NEA_ONLINE": "If checked, try the NASA TAP service first and fall "
                            "back to the local CSV on failure.",
        "NEA_FETCH_TIMEOUT": "Seconds to wait for the online TAP response.",
        "CATALOG_DIR": "Directory holding the PS_latest_{source}.csv cache files.",
    },
    "Filters": {
        "DESERT_FILTER": "Restrict to planets inside ('desert') / outside "
                        "('nondesert') the Neptunian-desert polygon, or 'all'.",
        "EXTRA_FILTERS": "Sequential AND filters on catalog columns. Each row "
                        "keeps rows where column is within [min, max] (or, with "
                        "'contains', where the column text matches).",
    },
    "Observatory": {
        "preset": "Pick a built-in telescope/instrument to auto-fill every field "
                  "below, or 'New' to enter your own values.",
        "name": "Short label used in output filenames.",
        "telescope": "Telescope name (documentation only).",
        "instrument": "Instrument name (documentation only).",
        "lat": "Observatory latitude [degrees, +N].",
        "lon": "Observatory longitude [degrees, +E].",
        "alt": "Observatory altitude [metres].",
        "timezone": "IANA timezone name (e.g. America/Santiago) for local-time axes.",
    },
    "Constraints": {
        "start": "Proposal window start date (YYYY-MM-DD).",
        "end": "Proposal window end date (YYYY-MM-DD).",
        "min_target_alt": "Minimum target elevation [deg] for observability.",
        "max_sun_alt": "Maximum Sun altitude [deg]; -10 is NEA twilight, -18 is "
                       "astronomical night.",
        "moon_dist_factor": "Moon-distance guard (0 disables the check).",
        "transit": "Fraction of the transit that must be observable (1.0 = full).",
        "pre_eclipse": "Fraction of the pre-eclipse window that must be observable.",
        "post_eclipse": "Fraction of the post-eclipse window that must be observable.",
        "TIME_RESOLUTION_MIN": "Grid step [minutes] for the night-by-night sampling.",
        "PRESELECTION_MIN_YEAR": "Only planets whose oldest reference year exceeds "
                                 "this are listed in preselection.csv.",
    },
    "Custom Planets": {
        "CUSTOM_PLANETS": "A JSON list of hand-entered targets injected into the "
                          "schedule in addition to the filtered catalog. Each list "
                          "item is one planet object. Leave as [] to schedule only "
                          "the catalog. For a target already in the catalog, any "
                          "field you set here overrides the catalog value.",
        "pl_name": "Planet name (required); also used for the output subfolder.",
        "pl_orbper": "Orbital period [days], sets the phase/ephemeris.",
        "pl_rade": "Planet radius [R_earth].",
        "pl_bmasse": "Planet mass [M_earth]; if omitted a mass-radius relation is used.",
        "pl_eqt": "Equilibrium temperature [K] (drives TSM/ESM).",
        "st_teff": "Stellar effective temperature [K].",
        "st_mass": "Stellar mass [M_sun] (needed for the Kp computation).",
        "st_rad": "Stellar radius [R_sun].",
        "st_jmag / st_kmag": "Stellar J / K magnitudes (feed TSM/ESM).",
        "ra / dec": "Right ascension / declination [deg] (needed for visibility).",
        "pl_tranmid": "Transit mid-time [BJD] (needed for the ephemeris).",
        "pl_orbsmax": "Semi-major axis [AU] (optional; else from Kepler's 3rd law).",
        "pl_orbeccen": "Orbital eccentricity (optional). Leave it null, or "
                       "omit it, to treat the orbit as circular; that is also "
                       "what happens below 0.01, where the eccentric and "
                       "circular radial-velocity traces are indistinguishable.",
        "pl_orblper": "Argument of periastron of the planet [deg] (optional). "
                      "Leave it null, or omit it, when it is unknown: with a "
                      "non-zero eccentricity the planetary radial velocity is "
                      "then shown as an envelope over all possible values "
                      "rather than assuming one, and the transit geometry "
                      "(T14, phi_sec) is flagged as unreliable in the log.",
        "v_sys": "Systemic radial velocity [km/s] for the telluric-overlap plot.",
        "Buttons": "Validate JSON checks the text parses; Insert example appends a "
                   "template planet; Clear empties the list.",
    },
    "Telluric": {
        "SKY_TRANSMISSION_FITS": "Sky-transmission FITS for the telluric-overlap "
                                 "page. Leave blank to disable that page.",
        "TELLURIC_LAMBDA_RANGE_NM": "Wavelength slice (start, stop) [nm] to display.",
        "TELLURIC_RV_GRID_KMS": "Radial-velocity grid (start, stop, step) [km/s].",
        "TELLURIC_PAD_HOURS": "Hours padded either side of the synthetic window.",
        "TELLURIC_EXP_TIME_S": "Synthetic exposure cadence [seconds].",
    },
    "Run": {
        "Overview": "This tab runs the scheduling pipeline with the current form "
                    "values and shows its progress. Settings are collected from "
                    "all other tabs, written to a settings.json inside OUTPUT_DIR, "
                    "and executed in a background process.",
        "Run": "Collect the configuration and start the pipeline. Disabled while a "
               "run is in progress. If OUTPUT_DIR already holds results, a prompt "
               "asks whether to delete them and run a fresh search (No cancels "
               "without starting).",
        "Stop": "Terminate the running pipeline process.",
        "Save preset": "Write the current form values to a JSON file you choose.",
        "Load preset": "Repopulate every tab from a previously saved JSON preset.",
        "Reset defaults": "Restore all fields to the bundled default configuration.",
        "Pipeline log": "Live standard output of the pipeline (catalog loading, "
                        "per-planet events, saved files, warnings).",
        "Generated files": "The PDFs / CSVs produced by the run. Double-click a row "
                           "to open that file in your system viewer.",
    },
    "Output & Plot": {
        "OUTPUT_DIR": "Root folder for all generated PDFs / CSVs.",
        "AUX_DIR": "Folder holding desert_boundaries.txt and the KDE npz.",
        "DESERT_BOUNDARY_FILE": "Castro-Gonzalez (2024) desert polygon file.",
        "KDE_FILE": "KDE background density for the period-radius landscape.",
        "P_MAX": "Landscape x-axis (period) upper limit [days].",
        "R_MAX": "Landscape y-axis (radius) upper limit [R_earth].",
    },
}


# --------------------------------------------------------------------------- #
#  Defaults
# --------------------------------------------------------------------------- #
def load_defaults() -> Dict[str, Any]:
    """Return a deep copy of every exposed config global's default value."""
    pc = _import_phase_config()
    defaults: Dict[str, Any] = {}
    for key in CONFIG_KEYS:
        defaults[key] = copy.deepcopy(getattr(pc, key))
    # Normalise tuples to lists so the value round-trips through the GUI/JSON.
    for key in ("TELLURIC_LAMBDA_RANGE_NM", "TELLURIC_RV_GRID_KMS"):
        defaults[key] = list(defaults[key])
    return defaults


# --------------------------------------------------------------------------- #
#  JSON serialisation
# --------------------------------------------------------------------------- #
def normalise(values: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-serialisable copy (tuples -> lists)."""
    out = copy.deepcopy(values)
    for key in ("TELLURIC_LAMBDA_RANGE_NM", "TELLURIC_RV_GRID_KMS"):
        if key in out and isinstance(out[key], tuple):
            out[key] = list(out[key])
    return out


def write_settings(path: str, values: Dict[str, Any]) -> None:
    with open(path, "w") as f:
        json.dump(normalise(values), f, indent=2)


def read_settings(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return json.load(f)
