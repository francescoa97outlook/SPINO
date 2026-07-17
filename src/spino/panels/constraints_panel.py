"""Constraints tab: date range, observing constraints, event coverage, sampling."""
from __future__ import annotations

from typing import Any, Dict

from spino import config_io
from spino.panels.base import FieldGrid, to_float, to_int


class ConstraintsPanel:
    KEYS = ["DATE_RANGE", "CONSTRAINTS", "EVENT_CONSTRAINTS",
            "TIME_RESOLUTION_MIN", "PRESELECTION_MIN_YEAR"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        g = FieldGrid(tab, bg, "Time & Constraints", config_io.HELP["Constraints"])

        g.section("Proposal window")
        dr = defaults["DATE_RANGE"]
        self._start = g.entry("start (YYYY-MM-DD)", dr["start"])
        self._end = g.entry("end (YYYY-MM-DD)", dr["end"])

        g.section("Observing constraints")
        c = defaults["CONSTRAINTS"]
        self._alt = g.entry("min_target_alt [deg]", c["min_target_alt"])
        self._sun = g.entry("max_sun_alt [deg]", c["max_sun_alt"])
        self._moon = g.entry("moon_dist_factor (0 = off)", c["moon_dist_factor"])

        g.section("Event coverage (fraction observable)")
        ec = defaults["EVENT_CONSTRAINTS"]
        self._tr = g.entry("transit min_coverage", ec["transit"]["min_coverage"])
        self._pre = g.entry("pre_eclipse min_coverage", ec["pre_eclipse"]["min_coverage"])
        self._post = g.entry("post_eclipse min_coverage", ec["post_eclipse"]["min_coverage"])

        g.section("Sampling & preselection")
        self._res = g.entry("TIME_RESOLUTION_MIN [min]", defaults["TIME_RESOLUTION_MIN"])
        self._year = g.entry("PRESELECTION_MIN_YEAR", defaults["PRESELECTION_MIN_YEAR"])

    def collect(self) -> Dict[str, Any]:
        return {
            "DATE_RANGE": {"start": self._start.get_value().strip(),
                           "end": self._end.get_value().strip()},
            "CONSTRAINTS": {
                "min_target_alt": to_float(self._alt.get_value(), 20.0),
                "max_sun_alt": to_float(self._sun.get_value(), -10.0),
                "moon_dist_factor": to_float(self._moon.get_value(), 0.0),
            },
            "EVENT_CONSTRAINTS": {
                "transit": {"min_coverage": to_float(self._tr.get_value(), 1.0)},
                "pre_eclipse": {"min_coverage": to_float(self._pre.get_value(), 0.5)},
                "post_eclipse": {"min_coverage": to_float(self._post.get_value(), 0.5)},
            },
            "TIME_RESOLUTION_MIN": to_int(self._res.get_value(), 2),
            "PRESELECTION_MIN_YEAR": to_int(self._year.get_value(), 2018),
        }

    def set_values(self, v: Dict[str, Any]) -> None:
        self._start.set_value(v["DATE_RANGE"]["start"])
        self._end.set_value(v["DATE_RANGE"]["end"])
        c = v["CONSTRAINTS"]
        self._alt.set_value(c["min_target_alt"])
        self._sun.set_value(c["max_sun_alt"])
        self._moon.set_value(c["moon_dist_factor"])
        ec = v["EVENT_CONSTRAINTS"]
        self._tr.set_value(ec["transit"]["min_coverage"])
        self._pre.set_value(ec["pre_eclipse"]["min_coverage"])
        self._post.set_value(ec["post_eclipse"]["min_coverage"])
        self._res.set_value(v["TIME_RESOLUTION_MIN"])
        self._year.set_value(v["PRESELECTION_MIN_YEAR"])
