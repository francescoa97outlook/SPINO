"""
theme: colour palette and tab list for the SPINO GUI.

Replaces GUIBRUSHR's domain-coupled ``ConstantVariables``: none of the copied
widgets need that module, they only need a colour per panel and (for the
notebook) a list of ``(tab_name, tab_colour)`` tuples.
"""

# Window / panel colours (Nord-inspired light palette; readable in both themes).
COLOR_WINDOW = "#ECEFF4"
COLOR_PANEL = "#E5E9F0"
COLOR_HEADER = "#4C566A"

# Button colours
COLOR_BUTTON = "#5E81AC"     # neutral action
COLOR_RUN = "#A3BE8C"        # green
COLOR_STOP = "#BF616A"       # red
COLOR_SECONDARY = "#81A1C1"  # save / load / reset

# Pipeline log colours (tags applied to the dark log Text widget on the Run tab).
LOG_BG = "#2E3440"          # log background (Nord polar night)
LOG_FG = "#D8DEE9"          # default log text
LOG_PHASE = "#88C0D0"       # phase banners  » [n/5] …
LOG_PLANET = "#EBCB8B"      # per-planet header (==== <name> ====)
LOG_SEP = "#4C566A"         # separator ==== lines (dim)
LOG_WARN = "#D08770"        # warnings (⚠)
LOG_OK = "#A3BE8C"          # success (✔, summary →, Calendar:, PRESELECTION →)
LOG_TOTAL = "#A3BE8C"       # final TOTAL line (bold)
LOG_CMD = "#616E88"         # command echo / bracketed GUI status ($ …, [finished])

# Notebook tabs: (label, panel background colour).
TABS = [
    ("Catalog", COLOR_PANEL),
    ("Filters", COLOR_PANEL),
    ("Observatory", COLOR_PANEL),
    ("Constraints", COLOR_PANEL),
    ("Custom Planets", COLOR_PANEL),
    ("Telluric", COLOR_PANEL),
    ("Output & Plot", COLOR_PANEL),
    ("Run", COLOR_PANEL),
]
