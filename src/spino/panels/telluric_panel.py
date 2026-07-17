"""Telluric tab - sky-transmission FITS and the telluric-overlap plot grid."""
from __future__ import annotations

from typing import Any, Dict

from spino import config_io
from spino.panels.base import FieldGrid, to_float


class TelluricPanel:
    KEYS = ["SKY_TRANSMISSION_FITS", "TELLURIC_LAMBDA_RANGE_NM",
            "TELLURIC_RV_GRID_KMS", "TELLURIC_PAD_HOURS", "TELLURIC_EXP_TIME_S"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        g = FieldGrid(tab, bg, "Telluric position plot", config_io.HELP["Telluric"])
        self._fits = g.path("SKY_TRANSMISSION_FITS (blank = disable)",
                            defaults["SKY_TRANSMISSION_FITS"], mode="file")

        g.section("Wavelength slice [nm]")
        lam = defaults["TELLURIC_LAMBDA_RANGE_NM"]
        self._lam0 = g.entry("lambda start", lam[0])
        self._lam1 = g.entry("lambda stop", lam[1])

        g.section("RV grid [km/s]")
        rv = defaults["TELLURIC_RV_GRID_KMS"]
        self._rv0 = g.entry("rv start", rv[0])
        self._rv1 = g.entry("rv stop (inclusive)", rv[1])
        self._rv2 = g.entry("rv step", rv[2])

        g.section("Synthetic window")
        self._pad = g.entry("TELLURIC_PAD_HOURS", defaults["TELLURIC_PAD_HOURS"])
        self._exp = g.entry("TELLURIC_EXP_TIME_S", defaults["TELLURIC_EXP_TIME_S"])

    def collect(self) -> Dict[str, Any]:
        return {
            "SKY_TRANSMISSION_FITS": self._fits.get_value().strip(),
            "TELLURIC_LAMBDA_RANGE_NM": [to_float(self._lam0.get_value(), 0.0),
                                         to_float(self._lam1.get_value(), 0.0)],
            "TELLURIC_RV_GRID_KMS": [to_float(self._rv0.get_value(), -50.0),
                                     to_float(self._rv1.get_value(), 50.0),
                                     to_float(self._rv2.get_value(), 1.5)],
            "TELLURIC_PAD_HOURS": to_float(self._pad.get_value(), 1.0),
            "TELLURIC_EXP_TIME_S": to_float(self._exp.get_value(), 300.0),
        }

    def set_values(self, v: Dict[str, Any]) -> None:
        self._fits.set_value(v["SKY_TRANSMISSION_FITS"])
        lam = v["TELLURIC_LAMBDA_RANGE_NM"]
        self._lam0.set_value(lam[0]); self._lam1.set_value(lam[1])
        rv = v["TELLURIC_RV_GRID_KMS"]
        self._rv0.set_value(rv[0]); self._rv1.set_value(rv[1]); self._rv2.set_value(rv[2])
        self._pad.set_value(v["TELLURIC_PAD_HOURS"])
        self._exp.set_value(v["TELLURIC_EXP_TIME_S"])
