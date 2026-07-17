"""Catalog tab — source, online-fetch toggle, timeout, cache directory."""
from __future__ import annotations

from typing import Any, Dict

from spino import config_io
from spino.panels.base import FieldGrid, to_int


class CatalogPanel:
    KEYS = ["CATALOG_SOURCE", "FETCH_NEA_ONLINE", "NEA_FETCH_TIMEOUT", "CATALOG_DIR"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        g = FieldGrid(tab, bg, "Catalog", config_io.HELP["Catalog"])
        self._source = g.dropdown("CATALOG_SOURCE", config_io.CATALOG_SOURCES,
                                  defaults["CATALOG_SOURCE"])
        self._online = g.checkbox("FETCH_NEA_ONLINE (try TAP, fall back to CSV)",
                                  defaults["FETCH_NEA_ONLINE"])
        self._timeout = g.entry("NEA_FETCH_TIMEOUT [s]", defaults["NEA_FETCH_TIMEOUT"])
        self._catdir = g.path("CATALOG_DIR", defaults["CATALOG_DIR"], mode="dir")

    def collect(self) -> Dict[str, Any]:
        return {
            "CATALOG_SOURCE": self._source.get_value(),
            "FETCH_NEA_ONLINE": bool(self._online.get_value()),
            "NEA_FETCH_TIMEOUT": to_int(self._timeout.get_value(), 30),
            "CATALOG_DIR": self._catdir.get_value().strip(),
        }

    def set_values(self, v: Dict[str, Any]) -> None:
        self._source.set_value(v["CATALOG_SOURCE"])
        self._online.set_value(1 if v["FETCH_NEA_ONLINE"] else 0)
        self._timeout.set_value(v["NEA_FETCH_TIMEOUT"])
        self._catdir.set_value(v["CATALOG_DIR"])
