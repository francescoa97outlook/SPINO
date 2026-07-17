"""
app: the SPINO main window.

Builds a tabbed window (one tab per configuration group + a Run tab) from the
reused GUIBRUSHR widget toolkit, and orchestrates the pipeline via the Run tab.
Launch with ``python -m spino`` or the ``spino`` console entry point.
"""
from __future__ import annotations

import copy
import os
import tkinter as tk
from typing import Any, Dict, List

from spino import config_io, theme

# Packaged application logo, used as the window icon.
LOGO_PATH = os.path.join(os.path.dirname(__file__), "data", "assets", "spino_logo.png")
from spino.gui_toolkit.layout.ScaleManager import ScaleManager
from spino.gui_toolkit.layout.MyTabPanel import MyTabPanel
from spino.panels.catalog_panel import CatalogPanel
from spino.panels.filters_panel import FiltersPanel
from spino.panels.observatory_panel import ObservatoryPanel
from spino.panels.constraints_panel import ConstraintsPanel
from spino.panels.custom_planets_panel import CustomPlanetsPanel
from spino.panels.telluric_panel import TelluricPanel
from spino.panels.output_panel import OutputPanel
from spino.panels.run_panel import RunPanel


class PhaseSchedulerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("SPINO")
        self._set_window_icon(root)
        root.configure(bg=theme.COLOR_WINDOW)
        root.geometry("1560x820")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        ScaleManager.init(root)

        self._defaults = config_io.load_defaults()

        notebook = MyTabPanel(root, 0, 0, theme.TABS)
        tabs = notebook.get_list()   # one MyPanel per tab, in TABS order

        d = self._defaults
        self._config_panels = [
            CatalogPanel(tabs[0], theme.COLOR_PANEL, d),
            FiltersPanel(tabs[1], theme.COLOR_PANEL, d),
            ObservatoryPanel(tabs[2], theme.COLOR_PANEL, d),
            ConstraintsPanel(tabs[3], theme.COLOR_PANEL, d),
            CustomPlanetsPanel(tabs[4], theme.COLOR_PANEL, d),
            TelluricPanel(tabs[5], theme.COLOR_PANEL, d),
            OutputPanel(tabs[6], theme.COLOR_PANEL, d),
        ]
        # Run tab (index 7) gets orchestration callbacks.
        self._run_panel = RunPanel(
            tabs[7], theme.COLOR_PANEL,
            collect_all=self.collect_all,
            apply_all=self.apply_all,
            defaults=copy.deepcopy(self._defaults),
        )

    def _set_window_icon(self, root: tk.Tk) -> None:
        """Set the window/taskbar icon from the packaged logo, if available."""
        try:
            self._icon = tk.PhotoImage(file=LOGO_PATH)
            root.iconphoto(True, self._icon)
        except Exception:
            # Missing file or a Tk build without PNG support: run without an icon.
            pass

    # -- orchestration ----------------------------------------------------- #
    def collect_all(self) -> Dict[str, Any]:
        """Merge every config panel's values into one settings dict.

        Raises ValueError (surfaced by the Run panel) if a panel cannot parse
        its input (e.g. malformed CUSTOM_PLANETS JSON).
        """
        merged: Dict[str, Any] = {}
        for panel in self._config_panels:
            merged.update(panel.collect())
        return merged

    def apply_all(self, values: Dict[str, Any]) -> None:
        """Distribute a (possibly partial) settings dict back to the panels."""
        full = copy.deepcopy(self._defaults)
        full.update(values)
        for panel in self._config_panels:
            panel.set_values(full)


def main() -> None:
    root = tk.Tk()
    PhaseSchedulerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
