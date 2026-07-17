"""Filters tab — desert filter + an editable EXTRA_FILTERS table."""
from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, List

from spino import config_io
from spino.gui_toolkit.widget.MyLabel import MyLabel
from spino.gui_toolkit.widget.MyEntry import MyEntry
from spino.gui_toolkit.widget.MyDropDown import MyDropdown
from spino.gui_toolkit.widget.MyButton import MyButton
from spino.gui_toolkit.widget.MyTable import MyTable
from spino.gui_toolkit.widget.HelpButton import HelpButton
from spino.panels.base import opt_float


_COLUMNS = ["column", "min", "max", "contains"]
_WIDTHS = [150, 100, 100, 160]


class FiltersPanel:
    KEYS = ["DESERT_FILTER", "EXTRA_FILTERS"]

    def __init__(self, tab, bg: str, defaults: Dict[str, Any]):
        frame = tk.Frame(tab, bg=bg)
        frame.grid(row=0, column=0, columnspan=101, sticky="nsew", padx=8, pady=8)
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(100, weight=0)
        frame.grid_columnconfigure(0, weight=1)

        header = MyLabel(frame, 0, 0, color=bg, label_text="Filters")
        try:
            header.label.config(font=("Sans", 20, "bold"))
        except Exception:
            pass
        HelpButton(frame, 0, 1, "Filters", config_io.HELP["Filters"])

        self._desert = MyDropdown(frame, 1, 0, config_io.DESERT_FILTERS,
                                  label_text="DESERT_FILTER", color=bg,
                                  initial_value=config_io.DESERT_FILTERS.index(
                                      defaults["DESERT_FILTER"]))

        MyLabel(frame, 2, 0, color=bg,
                label_text="EXTRA_FILTERS (applied sequentially, AND):")

        # Table in its own frame (MyTable .pack()s itself).
        table_frame = tk.Frame(frame, bg=bg)
        table_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=4)
        frame.grid_rowconfigure(3, weight=1)
        self._table = MyTable(table_frame, _COLUMNS, _WIDTHS, height=8)

        # Row editor
        editor = tk.Frame(frame, bg=bg)
        editor.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
        # Each labelled widget spans 2 parent columns (label + field), so place
        # them 2 columns apart to avoid overlap.
        self._col = MyDropdown(editor, 0, 0, config_io.FILTER_COLUMNS,
                               label_text="column", color=bg)
        self._min = MyEntry(editor, 0, 2, text="", label_text="min", color=bg,
                            entry_width=8)
        self._max = MyEntry(editor, 0, 4, text="", label_text="max", color=bg,
                            entry_width=8)
        self._contains = MyEntry(editor, 0, 6, text="", label_text="contains",
                                 color=bg, entry_width=12)
        MyButton(editor, 0, 8, "Add row", "#A3BE8C", self._add_row, color_panel=bg)
        MyButton(frame, 5, 0, "Remove selected", "#BF616A", self._remove_selected,
                 color_panel=bg)

        self.set_values(defaults)

    # -- table helpers ----------------------------------------------------- #
    def _add_row(self):
        col = self._col.get_value()
        self._table.insert("", "end", values=(
            col, self._min.get_value().strip(),
            self._max.get_value().strip(), self._contains.get_value().strip()))
        self._min.set_value(""); self._max.set_value(""); self._contains.set_value("")

    def _remove_selected(self):
        for iid in self._table.selection():
            self._table.delete(iid)

    def _clear(self):
        for iid in self._table.get_children():
            self._table.delete(iid)

    # -- collect / load ---------------------------------------------------- #
    def collect(self) -> Dict[str, Any]:
        filters: List[Dict[str, Any]] = []
        for iid in self._table.get_children():
            col, vmin, vmax, contains = self._table.item(iid)["values"]
            col = str(col).strip()
            if not col:
                continue
            row: Dict[str, Any] = {"column": col}
            contains = str(contains).strip()
            if contains:
                row["contains"] = contains
            else:
                fmin = opt_float(vmin)
                fmax = opt_float(vmax)
                if fmin is not None:
                    row["min"] = fmin
                if fmax is not None:
                    row["max"] = fmax
            filters.append(row)
        return {"DESERT_FILTER": self._desert.get_value(),
                "EXTRA_FILTERS": filters}

    def set_values(self, v: Dict[str, Any]) -> None:
        self._desert.set_value(v["DESERT_FILTER"])
        self._clear()
        for f in v.get("EXTRA_FILTERS", []):
            self._table.insert("", "end", values=(
                f.get("column", ""),
                f.get("min", ""),
                f.get("max", ""),
                f.get("contains", "")))
