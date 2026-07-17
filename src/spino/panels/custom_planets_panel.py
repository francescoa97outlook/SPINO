"""Custom Planets tab: a validated JSON editor for the CUSTOM_PLANETS list.

CUSTOM_PLANETS entries carry up to ~16 heterogeneous fields, so a free-form
JSON editor (with validation + an example inserter) is clearer and safer than
a 16-column table. Leave it as ``[]`` to schedule only the filtered catalog.
"""
from __future__ import annotations

import json
import tkinter as tk
from typing import Any, Dict, List

from spino import config_io
from spino.gui_toolkit.layout.ScaleManager import ScaleManager
from spino.gui_toolkit.widget.MyLabel import MyLabel
from spino.gui_toolkit.widget.MyButton import MyButton
from spino.gui_toolkit.widget.HelpButton import HelpButton


_EXAMPLE = {
    "pl_name": "HD 63433 b", "pl_orbper": 7.1079384, "pl_rade": 2.16351593,
    "pl_bmasse": 37.3, "pl_eqt": 886.4, "st_teff": 5634.0, "st_mass": 0.9883,
    "st_rad": 0.9169, "st_jmag": 5.624, "st_kmag": 5.258, "ra": 117.4793699,
    "dec": 27.3631342, "pl_tranmid": 2458845.37353, "pl_orbsmax": 0.072,
    "pl_orbeccen": 0.0, "v_sys": -15.856,
}


class CustomPlanetsPanel:
    KEYS = ["CUSTOM_PLANETS"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        frame = tk.Frame(tab, bg=bg)
        frame.grid(row=0, column=0, columnspan=101, sticky="nsew", padx=8, pady=8)
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(100, weight=0)
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        header = MyLabel(frame, 0, 0, color=bg, label_text="Custom Planets")
        try:
            header.label.config(font=("Sans", 20, "bold"))
        except Exception:
            pass
        HelpButton(frame, 0, 1, "Custom Planets", config_io.HELP["Custom Planets"])
        MyLabel(frame, 1, 0, color=bg,
                label_text="CUSTOM_PLANETS: JSON list of planet dicts "
                           f"(fields: pl_name, {', '.join(config_io.CUSTOM_PLANET_FIELDS)}):")

        text_frame = tk.Frame(frame, bg=bg)
        text_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        vsb = tk.Scrollbar(text_frame, orient="vertical")
        sm = ScaleManager.get()
        self._text = tk.Text(text_frame, wrap="none", undo=True,
                             yscrollcommand=vsb.set,
                             font=(sm.font_entry if sm else ("Courier", 10)))
        vsb.config(command=self._text.yview)
        self._text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        btns = tk.Frame(frame, bg=bg)
        btns.grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)
        MyButton(btns, 0, 0, "Validate JSON", "#81A1C1", self._validate,
                 color_panel=bg)
        MyButton(btns, 0, 1, "Insert example", "#A3BE8C", self._insert_example,
                 color_panel=bg)
        MyButton(btns, 0, 2, "Clear", "#BF616A", lambda: self._set_text([]),
                 color_panel=bg)
        self._status = MyLabel(frame, 4, 0, color=bg, label_text="", columnspan=2)

        self.set_values(defaults)

    # -- helpers ----------------------------------------------------------- #
    def _set_text(self, obj: List[dict]) -> None:
        self._text.delete("1.0", tk.END)
        self._text.insert(tk.END, json.dumps(obj, indent=2))

    def _insert_example(self):
        try:
            current = self._parse()
        except ValueError:
            current = []
        current.append(dict(_EXAMPLE))
        self._set_text(current)
        self._status.set_text("Example appended.")

    def _parse(self) -> List[dict]:
        raw = self._text.get("1.0", tk.END).strip()
        if not raw:
            return []
        data = json.loads(raw)
        if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
            raise ValueError("CUSTOM_PLANETS must be a JSON list of objects.")
        return data

    def _validate(self):
        try:
            n = len(self._parse())
            self._status.set_text(f"OK: {n} planet(s).")
        except ValueError as exc:
            self._status.set_text(f"Invalid JSON: {exc}")

    # -- collect / load ---------------------------------------------------- #
    def collect(self) -> Dict[str, Any]:
        return {"CUSTOM_PLANETS": self._parse()}

    def set_values(self, v: Dict[str, Any]) -> None:
        self._set_text(v.get("CUSTOM_PLANETS", []))
