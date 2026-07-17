"""
Phase Scheduler — User Configuration
=====================================
All user-facing settings for the phase scheduler tool.
Edit this file only; phase_scheduler.py imports it.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))   # .../spino/pipeline
_PKG = os.path.dirname(_HERE)                          # .../spino
_DATA = os.path.join(_PKG, "data")                     # bundled catalogs / aux / FITS

# ============================================================== #
#  CATALOG                                                        #
# ============================================================== #
# CATALOG_SOURCE selects which subset of the NASA Exoplanet Archive
# PS table is fetched and cached.  Each value caches to its own CSV
# inside CATALOG_DIR as PS_latest_{source}.csv.
#
#   "NEA"  — all confirmed planets (full PS table; default)
#   "TESS" — confirmed planets with disc_facility LIKE '%TESS%'
#   "BOTH" — same query as NEA, but the per-row catalog_source column
#            is derived from disc_facility (TESS or NEA per row).
#
#   FETCH_NEA_ONLINE  — try the TAP service first; on any failure the
#                       pipeline falls back to the local CSV.
#   NEA_FETCH_TIMEOUT — seconds to wait for the TAP response.
#   CATALOG_DIR       — directory holding PS_latest_{source}.csv files.
CATALOG_SOURCE    = "NEA"
FETCH_NEA_ONLINE  = False
NEA_FETCH_TIMEOUT = 30
CATALOG_DIR       = os.path.join(_DATA, "cat")

# "desert"    — keep only planets inside the desert polygon
# "nondesert" — keep only planets outside the desert polygon
# "all"       — no desert filter (keep all planets)
DESERT_FILTER = "all"

# Single-target run on HD 63433 b — keep the catalog pipeline silent by
# forcing an impossible filter so df_best is empty; HD 63433 b is then
# injected via CUSTOM_PLANETS below.  Restore the original block below to
# go back to the catalogue-wide run.
EXTRA_FILTERS = [
    {"column": "pl_orbper",  "min": 0,    "max": 7},
    {"column": "pl_eqt",     "min": 300,  "max": 2000},
    {"column": "pl_rade",    "min": 0,    "max": 15},
    {"column": "pl_bmasse",  "min": 15,   "max": 100},
    {"column": "dec",        "min": -50,   "max": 0},
    {"column": "sy_kmag",    "min": 0,    "max": 11},
]

# Original filters (restore to re-enable the curated catalogue run):
# EXTRA_FILTERS = [
#     {"column": "pl_orbper",  "min": 0,    "max": 15},
#     {"column": "pl_eqt",     "min": 600,  "max": 5000},
#     {"column": "pl_rade",    "min": 4,    "max": 30},
#     {"column": "pl_bmasse",  "min": 15,   "max": 200},
#     {"column": "sy_kmag",    "min": 0,    "max": 9},
#     {"column": "dec",        "min": 10,   "max": 45},
# ]

# ============================================================== #
#  PRESELECTION                                                   #
# ============================================================== #
# A symlink farm under OUTPUT_DIR/PRESELECTION is populated with the
# subset of qualifying planets:
#   - oldest reference's publication year > PRESELECTION_MIN_YEAR, AND
#   - at least one of TSM / ESM above its Kempton threshold.
PRESELECTION_MIN_YEAR = 2018

# ============================================================== #
#  OBSERVATORY                                                    #
# ============================================================== #
OBSERVATORY = {
    'name': 'VLT',                    # used as the output-filename label
    'telescope': 'VLT UT3 (Melipal)',
    'instrument': 'CRIRES+',
    'lat': -24.6275,                  # Cerro Paranal [deg]
    'lon': -70.4044,                  # [deg]
    'alt': 2635,                      # [m]
    'timezone': 'America/Santiago',
}
# OBSERVATORY = {
#     'name': 'TNG',
#     'telescope': 'TNG',
#     'instrument': 'GIANO-B',
#     'lat': 28.7569,
#     'lon': -17.8850,
#     'alt': 2387,
#     'timezone': 'Atlantic/Canary',
# }
# OBSERVATORY = {
#     'name': 'Gemini North',
#     'lat': 19.8238,
#     'lon': -155.4691,
#     'alt': 4213,
#     'timezone': 'Pacific/Honolulu',
# }
# ============================================================== #
#  OBSERVATION PERIOD                                             #
# ============================================================== #
DATE_RANGE = {'start': '2027-05-01', 'end': '2028-04-30'}

# ============================================================== #
#  OBSERVING CONSTRAINTS                                          #
# ============================================================== #
# Defaults aligned with NASA Exoplanet Archive's TransitView tool:
#   - target altitude  ≥ 20°   (NEA: "at least 20 degrees above")
#   - Sun altitude     ≤ -10°  (NEA: "at least 10 degrees below")
#   - moon constraint disabled (NEA shows but does not exclude based on moon).
# Tighten any of these for higher-quality observations (e.g. alt=50,
# sun=-18 for astronomical twilight, moon_dist_factor=0.8 for spectroscopy).
CONSTRAINTS = {
    'min_target_alt': 20.0,       # minimum target elevation [deg]
    'max_sun_alt':   -10.0,       # NEA TransitView default twilight [deg]
    'moon_dist_factor': 0.0,      # 0 disables moon distance check
}

# ============================================================== #
#  EVENT COVERAGE CONSTRAINTS                                     #
# ============================================================== #
# min_coverage: fraction of the event phase window that must fall
# within the observable night for the event to be scheduled.
# Transit kept at 1.0: only fully observable transits (deliberate user
# choice; lower to e.g. 0.5 or 0.0 to match NEA's partial-transit display).
EVENT_CONSTRAINTS = {
    'transit':      {'min_coverage': 1.0},   # 100 % (full transit)
    'pre_eclipse':  {'min_coverage': 0.5},   # 50 %
    'post_eclipse': {'min_coverage': 0.5},   # 50 %
}

# Single-target run on HD 63433 b.  Values pulled from the neptunian
# catalogue master.csv (Polanski 2024 ephemeris).  Re-enable the curated
# list by uncommenting the import + assignment below.
# from desert.neptunian_catalogue.curated_planets import as_phase_scheduler_list
# CUSTOM_PLANETS = as_phase_scheduler_list(only_complete=True)

CUSTOM_PLANETS = [
    # {
    #     "pl_name":     "HD 63433 b",
    #     "pl_orbper":   7.1079384,        # days
    #     "pl_rade":     2.16351593,       # R_earth
    #     "pl_bmasse":   37.3,             # M_earth
    #     "pl_eqt":      886.4,            # K
    #     "st_teff":     5634.0,           # K
    #     "st_mass":     0.9883,           # M_sun  (needed for Kp computation)
    #     "st_rad":      0.9169,           # R_sun
    #     "st_jmag":     5.624,
    #     "st_kmag":     5.258,
    #     "ra":          117.4793699,      # deg
    #     "dec":         27.3631342,       # deg
    #     "pl_tranmid":  2458845.37353,    # BJD
    #     "pl_orbsmax":  0.072,            # AU
    #     "pl_orbeccen": 0.0,
    #     "v_sys":      -15.856,           # km/s
    # },
]

# The hand-tuned entries below are kept as a reference for the format
# expected by phase_scheduler.  Append your own dict to CUSTOM_PLANETS
# below if you want to add a target outside the curated catalogue.
_HAND_TUNED_REFERENCE = [
    # {
    #     "pl_name":    "TOI-5108 b",
    #     "pl_orbper":  6.753581,         # days
    #     "pl_rade":    6.6,              # R_earth
    #     "pl_bmasse":  32.0,             # M_earth
    #     "pl_eqt":     1180.0,           # K
    #     "st_teff":    5808.0,           # K
    #     "st_rad":     1.29,             # R_sun
    #     "st_jmag":    8.612001,
    #     "st_kmag":    8.300,
    #     "ra":         166.269504,       # deg
    #     "dec":        11.246407,        # deg
    #     "pl_tranmid": 2459569.4778,     # BJD
    #     "v_sys":     -34.693,           # km/s
    # },
    # {
    #     "pl_name":    "TOI-5786 b",
    #     "pl_orbper":  12.779107,        # days
    #     "pl_rade":    8.54,             # R_earth
    #     "pl_bmasse":  73.0,             # M_earth
    #     "pl_eqt":     1040.0,           # K
    #     "st_teff":    6235.0,           # K
    #     "st_rad":     1.36,             # R_sun
    #     "st_jmag":    9.258,
    #     "st_kmag":    8.963,
    #     "ra":         293.322326,       # deg
    #     "dec":        30.704247,        # deg
    #     "pl_tranmid": 2460140.6139,     # BJD
    #     "v_sys":     -28.388,           # km/s
    # },
    # {
    #     "pl_name":    "My Planet b",
    #     "pl_orbper":  1.234,       # orbital period [days]
    #     "pl_rade":    3.5,         # planet radius  [R_earth]
    #     "pl_bmasse":  15.0,        # planet mass    [M_earth]
    #     "pl_eqt":     1800,        # equilibrium T  [K]
    #     "st_teff":    5200,        # stellar Teff   [K]
    #     "st_rad":     0.9,         # stellar radius [R_sun]
    #     "st_jmag":    8.5,         # J magnitude
    #     "st_kmag":    8.2,         # K magnitude
    #     "ra":         180.0,       # RA  [deg] (optional, for transit plots)
    #     "dec":        -20.0,       # Dec [deg] (optional, for transit plots)
    #     "pl_tranmid": 2459000.0,   # transit mid BJD (optional, for transit plots)
    #     "v_sys":      13.667,      # systemic RV [km/s] (optional, for the
    #                                # telluric position plot; overrides NEA
    #                                # st_radv when present).
    # },
    # {
    #     "pl_name":    "KELT-9b",
    #     "pl_orbper":  1.48111897,       # Kokori et al. [days]
    #     "pl_rade":    1.891 * 11.209,   # 1.891 Rjup → R_earth
    #     "pl_bmasse":  2.88 * 317.828,   # 2.88  Mjup → M_earth
    #     "pl_eqt":     4050.0,           # equilibrium T  [K]
    #     "st_teff":    10170.0,          # stellar Teff   [K]
    #     "st_rad":     2.362,            # stellar radius [R_sun]
    #     "st_jmag":    7.458,            # J magnitude
    #     "st_kmag":    7.482,            # K magnitude
    #     "ra":         300.7182,         # RA  [deg]
    #     "dec":        39.9434,          # Dec [deg]
    #     "pl_tranmid": 2459074.460549,   # Kokori et al. BJD_TDB
    #     "pl_orbsmax": 0.03462
    # },
]

# ============================================================== #
#  TELLURIC POSITION PLOT                                         #
# ============================================================== #
# A second page is appended to each per-event PDF showing where
# the GIANO-B sky-transmission spectrum (Earth frame) will fall
# in the stellar rest frame during the event. Set SKY_TRANSMISSION_FITS
# to "" to disable. vsys is taken from NEA st_radv and overridable
# per planet via "v_sys" in CUSTOM_PLANETS.
SKY_TRANSMISSION_FITS = os.path.join(_DATA, "sky_transmission.fits")
TELLURIC_LAMBDA_RANGE_NM = (2359.0, 2426.0)    # GIANO-B order zero
TELLURIC_RV_GRID_KMS     = (-50.0, 50.0, 1.5)  # (start, stop_inclusive, step)
TELLURIC_PAD_HOURS       = 1.0                 # synthetic window pad each side
TELLURIC_EXP_TIME_S      = 300.0               # synthetic exposure cadence

# ============================================================== #
#  TIME RESOLUTION                                                #
# ============================================================== #
TIME_RESOLUTION_MIN = 2   # minutes per grid step

# ============================================================== #
#  OUTPUT                                                         #
# ============================================================== #
# Default to a user-writable folder in the current working directory (never
# inside the installed package). Overridable from the GUI / settings.json.
OUTPUT_DIR = os.path.join(os.getcwd(), "phase_scheduler_output")

# ============================================================== #
#  DESERT PLOT                                                    #
# ============================================================== #
AUX_DIR = os.path.join(_DATA, "auxiliary")
DESERT_BOUNDARY_FILE = os.path.join(AUX_DIR, "desert_boundaries.txt")
KDE_FILE = os.path.join(AUX_DIR, "kde_points_NEA.npz")
P_MAX = 100
R_MAX = 20
