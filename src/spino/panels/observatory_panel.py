"""Observatory tab - name / telescope / instrument / lat / lon / alt / timezone."""
from __future__ import annotations

from typing import Any, Dict

from spino import config_io
from spino.panels.base import FieldGrid, to_float


class ObservatoryPanel:
    KEYS = ["OBSERVATORY"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        obs = defaults["OBSERVATORY"]
        g = FieldGrid(tab, bg, "Observatory", config_io.HELP["Observatory"])
        self._name = g.entry("name (used in filenames)", obs.get("name", ""))
        self._telescope = g.entry("telescope", obs.get("telescope", ""))
        self._instrument = g.entry("instrument", obs.get("instrument", ""))
        self._lat = g.entry("lat [deg, +N]", obs.get("lat", ""))
        self._lon = g.entry("lon [deg, +E]", obs.get("lon", ""))
        self._alt = g.entry("alt [m]", obs.get("alt", ""))
        tz = obs.get("timezone", "UTC")
        tz_options = list(dict.fromkeys(config_io.TIMEZONES + [tz]))
        self._tz = g.dropdown("timezone", tz_options, tz)

    def collect(self) -> Dict[str, Any]:
        return {"OBSERVATORY": {
            "name": self._name.get_value().strip(),
            "telescope": self._telescope.get_value().strip(),
            "instrument": self._instrument.get_value().strip(),
            "lat": to_float(self._lat.get_value(), 0.0),
            "lon": to_float(self._lon.get_value(), 0.0),
            "alt": to_float(self._alt.get_value(), 0.0),
            "timezone": self._tz.get_value(),
        }}

    def set_values(self, v: Dict[str, Any]) -> None:
        obs = v["OBSERVATORY"]
        self._name.set_value(obs.get("name", ""))
        self._telescope.set_value(obs.get("telescope", ""))
        self._instrument.set_value(obs.get("instrument", ""))
        self._lat.set_value(obs.get("lat", ""))
        self._lon.set_value(obs.get("lon", ""))
        self._alt.set_value(obs.get("alt", ""))
        self._tz.set_value(obs.get("timezone", "UTC"))
