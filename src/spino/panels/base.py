"""
base: shared helpers for the config panels.

* ``ScrollFrame``: a vertically scrollable container so a tab can hold more
  rows than fit on screen (extracted from GUIBRUSHR's ad-hoc Canvas+Scrollbar
  pattern into a small reusable class).
* ``FieldGrid``: a thin builder that lays out labelled ``My*`` widgets row by
  row inside a ScrollFrame and keeps references for read-back.
* numeric-cast helpers used by every panel's ``collect()``.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import Any, Callable, List, Optional

from spino.gui_toolkit.widget.MyLabel import MyLabel
from spino.gui_toolkit.widget.MyEntry import MyEntry
from spino.gui_toolkit.widget.MyDropDown import MyDropdown
from spino.gui_toolkit.widget.MyCheckBox import MyCheckBox
from spino.gui_toolkit.widget.MyButton import MyButton
from spino.gui_toolkit.widget.HelpButton import HelpButton


# --------------------------------------------------------------------------- #
#  numeric casting
# --------------------------------------------------------------------------- #
def to_int(text: str, default: Optional[int] = None) -> Optional[int]:
    text = str(text).strip()
    if text == "":
        return default
    return int(float(text))


def to_float(text: str, default: Optional[float] = None) -> Optional[float]:
    text = str(text).strip()
    if text == "":
        return default
    return float(text)


def opt_float(text: str) -> Optional[float]:
    """Return a float, or None for an empty field."""
    return to_float(text, default=None)


# --------------------------------------------------------------------------- #
#  scrollable container
# --------------------------------------------------------------------------- #
class ScrollFrame(tk.Frame):
    """A vertically scrollable frame; add widgets to ``.inner``."""

    def __init__(self, parent: Any, bg: str):
        super().__init__(parent, bg=bg)
        # MyPanel (the tab) pre-weights columns 0 and 100; the empty column 100
        # would otherwise reserve dead space on the right. Claim the full width.
        self.grid(row=0, column=0, columnspan=101, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(100, weight=0)

        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        vsb = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self._canvas, bg=bg)
        self._win = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._win, width=e.width),
        )
        # Mouse-wheel scrolling while the pointer is over the canvas.
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _bind_wheel(self, _event):
        self._canvas.bind_all("<Button-4>", self._on_wheel)
        self._canvas.bind_all("<Button-5>", self._on_wheel)
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event):
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")
        self._canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        if getattr(event, "num", None) == 4:
            self._canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-event.delta / 120), "units")


# --------------------------------------------------------------------------- #
#  field builder
# --------------------------------------------------------------------------- #
class FieldGrid:
    """Row-by-row builder for labelled input widgets inside a ScrollFrame."""

    def __init__(self, parent_tab: Any, bg: str, title: str,
                 help_text: Optional[dict] = None):
        self.bg = bg
        self.scroll = ScrollFrame(parent_tab, bg)
        self.inner = self.scroll.inner
        self.inner.grid_columnconfigure(1, weight=1)
        self._row = 0

        header = MyLabel(self.inner, self._row, 0, color=bg, label_text=title)
        try:
            header.label.config(font=("Sans", 20, "bold"))
        except Exception:
            pass
        if help_text:
            HelpButton(self.inner, self._row, 3, title, help_text)
        self._row += 1

    # -- section separator ------------------------------------------------- #
    def section(self, text: str) -> None:
        lbl = MyLabel(self.inner, self._row, 0, color=self.bg, label_text=text,
                      columnspan=3)
        try:
            lbl.label.config(font=("Sans", 15, "bold"), fg="#4C566A")
        except Exception:
            pass
        self._row += 1

    # -- widgets ----------------------------------------------------------- #
    def entry(self, label: str, value: Any, width: int = 22) -> MyEntry:
        w = MyEntry(self.inner, self._row, 0, text="" if value is None else value,
                    label_text=label, color=self.bg, entry_width=width,
                    columnspan=2)
        self._row += 1
        return w

    def dropdown(self, label: str, options: List[str], value: str) -> MyDropdown:
        idx = options.index(value) if value in options else 0
        w = MyDropdown(self.inner, self._row, 0, options, label_text=label,
                       color=self.bg, initial_value=idx, columnspan=2)
        self._row += 1
        return w

    def checkbox(self, label: str, value: bool) -> MyCheckBox:
        w = MyCheckBox(self.inner, self._row, 0, text=label,
                       initial_value=1 if value else 0)
        # Span all columns and stick west: a long checkbox label must not widen
        # the label column and push the other rows' entries to the right.
        w.grid_configure(columnspan=4, sticky="w")
        try:
            w.config(bg=self.bg)
            w.checkbox.config(bg=self.bg, activebackground=self.bg)
        except Exception:
            pass
        self._row += 1
        return w

    def path(self, label: str, value: Any, mode: str = "dir") -> MyEntry:
        """Label + entry + Browse button. mode: 'dir' | 'file'."""
        MyLabel(self.inner, self._row, 0, color=self.bg, label_text=label)
        entry = MyEntry(self.inner, self._row, 1, text="" if value is None else value,
                        color=self.bg, entry_width=40, columnspan=1)

        def browse():
            if mode == "dir":
                chosen = filedialog.askdirectory(initialdir=_start_dir(entry.get_value()))
            else:
                chosen = filedialog.askopenfilename(initialdir=_start_dir(entry.get_value()))
            if chosen:
                entry.set_value(chosen)

        MyButton(self.inner, self._row, 2, "Browse", "#81A1C1", browse,
                 color_panel=self.bg)
        self._row += 1
        return entry

    def button(self, label: str, colour: str, command: Callable,
               column: int = 0) -> MyButton:
        w = MyButton(self.inner, self._row, column, label, colour, command,
                     color_panel=self.bg)
        if column == 0:
            self._row += 1
        return w

    def image(self, path: str, max_width: int = 220) -> Optional[tk.PhotoImage]:
        """Centered image (e.g. the app logo) below the current rows."""
        frame = tk.Frame(self.inner, bg=self.bg)
        frame.grid(row=self._row, column=0, columnspan=5, sticky="ew", pady=(36, 4))
        frame.grid_columnconfigure(0, weight=1)
        self._row += 1

        img = tk.PhotoImage(file=path)
        if img.width() > max_width:
            factor = max(1, img.width() // max_width)
            img = img.subsample(factor, factor)
        lbl = tk.Label(frame, image=img, bg=self.bg)
        lbl.image = img  # keep a reference; Tk drops the image without it
        lbl.grid(row=0, column=0)
        return img

    def next_row(self) -> int:
        r = self._row
        self._row += 1
        return r

    @property
    def parent(self):
        return self.inner


def _start_dir(current: str) -> str:
    import os
    current = (current or "").strip()
    if current and os.path.isdir(current):
        return current
    if current and os.path.isfile(current):
        return os.path.dirname(current)
    d = os.path.dirname(current) if current else ""
    return d if d and os.path.isdir(d) else os.getcwd()
