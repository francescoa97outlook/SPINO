"""Observatory tab: a preset picker plus name / telescope / instrument / lat / lon / alt / timezone.

Selecting a built-in preset (CRIRES+, IGRINS-2, GIANO-B) auto-fills every field
from ``config_io.OBSERVATORY_PRESETS``. The trailing "New" entry lets the user
type custom values; editing any field also switches the picker to "New" so the
label always reflects what is in the fields.
"""
from __future__ import annotations

from typing import Any, Dict

from spino import config_io
from spino.panels.base import FieldGrid, to_float


def _close(a: Any, b: Any, tol: float = 1e-4) -> bool:
    """True if two numeric values match within ``tol`` (False if either is unparsable)."""
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


class ObservatoryPanel:
    KEYS = ["OBSERVATORY"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        obs = defaults["OBSERVATORY"]
        g = FieldGrid(tab, bg, "Observatory", config_io.HELP["Observatory"])

        self._presets = config_io.OBSERVATORY_PRESETS
        self._new = config_io.OBSERVATORY_PRESET_NEW
        preset_options = list(self._presets.keys()) + [self._new]

        # Guard so programmatic fills do not re-trigger each other's callbacks.
        self._suppress = False

        self._preset = g.dropdown("preset", preset_options, preset_options[0])

        self._name = g.entry("name (used in filenames)", obs.get("name", ""))
        self._telescope = g.entry("telescope", obs.get("telescope", ""))
        self._instrument = g.entry("instrument", obs.get("instrument", ""))
        self._lat = g.entry("lat [deg, +N]", obs.get("lat", ""))
        self._lon = g.entry("lon [deg, +E]", obs.get("lon", ""))
        self._alt = g.entry("alt [m]", obs.get("alt", ""))
        tz = obs.get("timezone", "UTC")
        tz_options = list(dict.fromkeys(config_io.TIMEZONES + [tz]))
        self._tz = g.dropdown("timezone", tz_options, tz)

        self._entries = [self._name, self._telescope, self._instrument,
                         self._lat, self._lon, self._alt]

        # Show the preset that matches the initial defaults (else "New").
        self._sync_preset_to_fields()

        # Wire callbacks after the initial sync so setup does not fire them.
        self._preset.set_callback(self._on_preset_change)
        for e in self._entries:
            e.entry.bind("<KeyRelease>", self._on_field_edited)
        self._tz.set_callback(self._on_tz_changed)

    # -- preset logic ------------------------------------------------------ #
    def _apply_preset(self, preset_name: str) -> None:
        p = self._presets[preset_name]
        self._suppress = True
        try:
            self._name.set_value(p["name"])
            self._telescope.set_value(p["telescope"])
            self._instrument.set_value(p["instrument"])
            self._lat.set_value(p["lat"])
            self._lon.set_value(p["lon"])
            self._alt.set_value(p["alt"])
            self._tz.set_value(p["timezone"])
        finally:
            self._suppress = False

    def _on_preset_change(self) -> None:
        if self._suppress:
            return
        choice = self._preset.get_value()
        if choice in self._presets:
            self._apply_preset(choice)
        # "New": leave the current field values for the user to edit.

    def _on_field_edited(self, _event=None) -> None:
        if self._suppress:
            return
        if self._preset.get_value() != self._new:
            self._set_preset_silent(self._new)

    def _on_tz_changed(self) -> None:
        if self._suppress:
            return
        if self._preset.get_value() != self._new:
            self._set_preset_silent(self._new)

    def _set_preset_silent(self, value: str) -> None:
        self._suppress = True
        try:
            self._preset.set_value(value)
        finally:
            self._suppress = False

    def _match_preset(self, obs: Dict[str, Any]) -> str:
        """Return the preset name whose values equal ``obs``, else "New"."""
        for pname, p in self._presets.items():
            if (str(obs.get("name", "")).strip() == p["name"]
                    and str(obs.get("instrument", "")).strip() == p["instrument"]
                    and _close(obs.get("lat"), p["lat"])
                    and _close(obs.get("lon"), p["lon"])
                    and _close(obs.get("alt"), p["alt"])
                    and str(obs.get("timezone", "")) == p["timezone"]):
                return pname
        return self._new

    def _sync_preset_to_fields(self) -> None:
        self._set_preset_silent(self._match_preset(self._current_obs()))

    def _current_obs(self) -> Dict[str, Any]:
        return {
            "name": self._name.get_value().strip(),
            "telescope": self._telescope.get_value().strip(),
            "instrument": self._instrument.get_value().strip(),
            "lat": to_float(self._lat.get_value(), 0.0),
            "lon": to_float(self._lon.get_value(), 0.0),
            "alt": to_float(self._alt.get_value(), 0.0),
            "timezone": self._tz.get_value(),
        }

    # -- panel API --------------------------------------------------------- #
    def collect(self) -> Dict[str, Any]:
        return {"OBSERVATORY": self._current_obs()}

    def set_values(self, v: Dict[str, Any]) -> None:
        obs = v["OBSERVATORY"]
        self._suppress = True
        try:
            self._name.set_value(obs.get("name", ""))
            self._telescope.set_value(obs.get("telescope", ""))
            self._instrument.set_value(obs.get("instrument", ""))
            self._lat.set_value(obs.get("lat", ""))
            self._lon.set_value(obs.get("lon", ""))
            self._alt.set_value(obs.get("alt", ""))
            self._tz.set_value(obs.get("timezone", "UTC"))
        finally:
            self._suppress = False
        self._sync_preset_to_fields()
