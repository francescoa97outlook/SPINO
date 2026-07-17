"""Output & Plot tab — output dir, aux/boundary/KDE paths, landscape limits."""
from __future__ import annotations

from typing import Any, Dict

from spino import config_io
from spino.panels.base import FieldGrid, to_int


class OutputPanel:
    KEYS = ["OUTPUT_DIR", "AUX_DIR", "DESERT_BOUNDARY_FILE", "KDE_FILE",
            "P_MAX", "R_MAX"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        g = FieldGrid(tab, bg, "Output & Plot", config_io.HELP["Output & Plot"])
        self._out = g.path("OUTPUT_DIR", defaults["OUTPUT_DIR"], mode="dir")

        g.section("Desert landscape inputs")
        self._aux = g.path("AUX_DIR", defaults["AUX_DIR"], mode="dir")
        self._boundary = g.path("DESERT_BOUNDARY_FILE",
                               defaults["DESERT_BOUNDARY_FILE"], mode="file")
        self._kde = g.path("KDE_FILE", defaults["KDE_FILE"], mode="file")

        g.section("Landscape axis limits")
        self._pmax = g.entry("P_MAX [days]", defaults["P_MAX"])
        self._rmax = g.entry("R_MAX [R_earth]", defaults["R_MAX"])

    def collect(self) -> Dict[str, Any]:
        return {
            "OUTPUT_DIR": self._out.get_value().strip(),
            "AUX_DIR": self._aux.get_value().strip(),
            "DESERT_BOUNDARY_FILE": self._boundary.get_value().strip(),
            "KDE_FILE": self._kde.get_value().strip(),
            "P_MAX": to_int(self._pmax.get_value(), 100),
            "R_MAX": to_int(self._rmax.get_value(), 20),
        }

    def set_values(self, v: Dict[str, Any]) -> None:
        self._out.set_value(v["OUTPUT_DIR"])
        self._aux.set_value(v["AUX_DIR"])
        self._boundary.set_value(v["DESERT_BOUNDARY_FILE"])
        self._kde.set_value(v["KDE_FILE"])
        self._pmax.set_value(v["P_MAX"])
        self._rmax.set_value(v["R_MAX"])
