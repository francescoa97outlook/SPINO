"""Run tab - save/load/reset, launch the pipeline subprocess, stream its log,
and list the generated output files (double-click opens them externally).
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, Optional

from spino import config_io, theme
from spino.gui_toolkit.layout.ScaleManager import ScaleManager
from spino.gui_toolkit.widget.MyLabel import MyLabel
from spino.gui_toolkit.widget.MyButton import MyButton
from spino.gui_toolkit.widget.MyTable import MyTable
from spino.gui_toolkit.widget.HelpButton import HelpButton

# src/ dir (parent of the spino package) - put on the child's
# PYTHONPATH so `python -m spino.runner` resolves when running
# from a source checkout (not just an installed package).
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.dirname(_PKG_DIR)


class RunPanel:
    """Injected with orchestration callbacks supplied by the app."""

    def __init__(self, tab, bg: str,
                 collect_all: Callable[[], Dict[str, Any]],
                 apply_all: Callable[[Dict[str, Any]], None],
                 defaults: Dict[str, Any]):
        self._collect_all = collect_all
        self._apply_all = apply_all
        self._defaults = defaults
        self._bg = bg
        self._proc: Optional[subprocess.Popen] = None
        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._output_dir: Optional[str] = None
        # planet-folder name → list of absolute file paths (filled after a run).
        self._planet_files: Dict[str, list] = {}

        frame = tk.Frame(tab, bg=bg)
        frame.grid(row=0, column=0, columnspan=101, sticky="nsew", padx=8, pady=8)
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(100, weight=0)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=3)
        frame.grid_rowconfigure(4, weight=2)
        self._frame = frame

        # -- action buttons ------------------------------------------------ #
        bar = tk.Frame(frame, bg=bg)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self._run_btn = MyButton(bar, 0, 0, "▶ Run", "#A3BE8C", self._on_run,
                                 color_panel=bg)
        self._stop_btn = MyButton(bar, 0, 1, "■ Stop", "#BF616A", self._on_stop,
                                  color_panel=bg)
        self._stop_btn.set_status("disabled")
        MyButton(bar, 0, 2, "Save preset", "#81A1C1", self._on_save, color_panel=bg)
        MyButton(bar, 0, 3, "Load preset", "#81A1C1", self._on_load, color_panel=bg)
        MyButton(bar, 0, 4, "Reset defaults", "#81A1C1", self._on_reset,
                 color_panel=bg)
        HelpButton(bar, 0, 5, "Run", config_io.HELP["Run"])

        # -- log ----------------------------------------------------------- #
        MyLabel(frame, 1, 0, color=bg, label_text="Pipeline log:")
        log_frame = tk.Frame(frame, bg=bg)
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        vsb = tk.Scrollbar(log_frame, orient="vertical")
        sm = ScaleManager.get()
        self._log = tk.Text(log_frame, height=14, wrap="word", state="disabled",
                            bg="#2E3440", fg="#D8DEE9",
                            yscrollcommand=vsb.set,
                            font=(sm.font_entry if sm else ("Courier", 10)))
        vsb.config(command=self._log.yview)
        self._log.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Colour tags: classify each log line so the run reads at a glance.
        base_font = sm.font_entry if sm else ("Courier", 10)
        if isinstance(base_font, tkfont.Font):        # ScaleManager Font object
            bold_font = base_font.copy()
            bold_font.configure(weight="bold")
        elif isinstance(base_font, tuple):            # ("Courier", 10)
            bold_font = (*base_font[:2], "bold")
        else:                                         # bare family string
            bold_font = (base_font, 10, "bold")
        self._log.tag_config("phase", foreground=theme.LOG_PHASE, font=bold_font)
        self._log.tag_config("planet", foreground=theme.LOG_PLANET, font=bold_font)
        self._log.tag_config("sep", foreground=theme.LOG_SEP)
        self._log.tag_config("warn", foreground=theme.LOG_WARN)
        self._log.tag_config("ok", foreground=theme.LOG_OK)
        self._log.tag_config("total", foreground=theme.LOG_TOTAL, font=bold_font)
        self._log.tag_config("cmd", foreground=theme.LOG_CMD)

        # -- output: planets (left) ↔ files (right) master-detail ---------- #
        panes = tk.PanedWindow(frame, orient="horizontal", bg=bg,
                               sashwidth=6, sashrelief="raised")
        panes.grid(row=4, column=0, sticky="nsew")

        left = tk.Frame(panes, bg=bg)
        MyLabel(left, 0, 0, color=bg,
                label_text="Planets found (double-click to see files):")
        left_tbl = tk.Frame(left, bg=bg)
        left_tbl.grid(row=1, column=0, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._planet_table = MyTable(left_tbl, ["planet"], [260], height=8)
        self._planet_table.bind("<Double-1>", self._on_select_planet)
        panes.add(left, stretch="always")

        right = tk.Frame(panes, bg=bg)
        MyLabel(right, 0, 0, color=bg,
                label_text="Files (double-click to open):")
        right_tbl = tk.Frame(right, bg=bg)
        right_tbl.grid(row=1, column=0, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self._file_table = MyTable(right_tbl, ["file"], [420], height=8)
        self._file_table.bind("<Double-1>", self._on_open_file)
        panes.add(right, stretch="always")

    # ===================================================================== #
    #  logging
    # ===================================================================== #
    @staticmethod
    def _classify(line: str) -> Optional[str]:
        """Pick a colour tag from the line's content (None = default colour)."""
        s = line.strip()
        if not s:
            return None
        if s.startswith("»"):
            return "phase"
        if s.startswith("●"):                    # ● <planet name> header
            return "planet"
        if set(s) <= {"="} and len(s) >= 3:      # ==== separator ====
            return "sep"
        if s.startswith("$") or (s.startswith("[") and s.endswith("]")):
            return "cmd"
        if "TOTAL:" in s:
            return "total"
        if "⚠" in s:
            return "warn"
        if "✔" in s or s.startswith(("summary →", "Calendar:", "PRESELECTION →")):
            return "ok"
        return None

    def _log_write(self, text: str, tag: Optional[str] = None) -> None:
        if tag is None:
            tag = self._classify(text)
        self._log.config(state="normal")
        self._log.insert(tk.END, text, tag or ())
        self._log.see(tk.END)
        self._log.config(state="disabled")

    def _clear_log(self) -> None:
        self._log.config(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.config(state="disabled")

    # ===================================================================== #
    #  run / stop
    # ===================================================================== #
    def _on_run(self) -> None:
        if self._proc is not None:
            return
        try:
            settings = self._collect_all()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self._output_dir = settings.get("OUTPUT_DIR")
        work_dir = self._output_dir or os.getcwd()
        os.makedirs(work_dir, exist_ok=True)
        settings_path = os.path.join(work_dir, "settings.json")
        config_io.write_settings(settings_path, settings)

        env = dict(os.environ)
        env["PYTHONPATH"] = _SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")

        self._clear_log()
        self._log_write(f"$ python -m spino.runner {settings_path}\n\n")
        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-u", "-m", "spino.runner",
                 settings_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env, cwd=work_dir,
            )
        except Exception as exc:  # pragma: no cover - launch failure
            messagebox.showerror("Launch failed", str(exc))
            self._proc = None
            return

        self._run_btn.set_status("disabled")
        self._stop_btn.set_status("normal")
        threading.Thread(target=self._reader, args=(self._proc,), daemon=True).start()
        self._frame.after(150, self._drain)

    def _reader(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                self._queue.put(line)
        finally:
            proc.wait()
            self._queue.put(None)  # sentinel: process finished

    def _drain(self) -> None:
        finished = False
        try:
            while True:
                item = self._queue.get_nowait()
                if item is None:
                    finished = True
                    break
                self._log_write(item)
        except queue.Empty:
            pass

        if finished:
            self._on_finished()
        else:
            self._frame.after(150, self._drain)

    def _on_finished(self) -> None:
        code = self._proc.returncode if self._proc else None
        self._proc = None
        self._run_btn.set_status("normal")
        self._stop_btn.set_status("disabled")
        self._log_write(f"\n[finished, exit code {code}]\n")
        self._refresh_outputs()

    def _on_stop(self) -> None:
        if self._proc is not None:
            self._log_write("\n[stopping…]\n")
            self._proc.terminate()

    # ===================================================================== #
    #  output listing
    # ===================================================================== #
    _GLOBAL = "◆ Global"

    def _refresh_outputs(self) -> None:
        """Group generated files by planet folder and list the planets left."""
        for iid in self._planet_table.get_children():
            self._planet_table.delete(iid)
        for iid in self._file_table.get_children():
            self._file_table.delete(iid)
        self._planet_files = {}
        if not self._output_dir or not os.path.isdir(self._output_dir):
            return

        for root, _dirs, files in os.walk(self._output_dir):
            for name in files:
                if not name.lower().endswith((".pdf", ".csv")):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, self._output_dir)
                head = rel.split(os.sep)[0]
                # Files directly under OUTPUT_DIR (e.g. PR_landscape.pdf) group
                # under a synthetic "Global" entry; everything else by folder.
                key = self._GLOBAL if head == rel else head
                self._planet_files.setdefault(key, []).append(path)

        # Global first, then planets alphabetically.
        keys = sorted(self._planet_files,
                      key=lambda k: (k != self._GLOBAL, k.lower()))
        for k in keys:
            n = len(self._planet_files[k])
            self._planet_table.insert("", "end", values=(f"{k}  ({n})",),
                                      tags=(k,))

    def _on_select_planet(self, _event) -> None:
        iid = self._planet_table.focus()
        if not iid:
            return
        tags = self._planet_table.item(iid).get("tags")
        if not tags:
            return
        key = tags[0]
        for fid in self._file_table.get_children():
            self._file_table.delete(fid)
        base = self._output_dir or ""
        if key != self._GLOBAL:
            base = os.path.join(base, key)
        for p in sorted(self._planet_files.get(key, [])):
            label = os.path.relpath(p, base)
            self._file_table.insert("", "end", values=(label,), tags=(p,))

    def _on_open_file(self, _event) -> None:
        iid = self._file_table.focus()
        if not iid:
            return
        tags = self._file_table.item(iid).get("tags")
        if not tags:
            return
        _open_external(tags[0])

    # ===================================================================== #
    #  presets
    # ===================================================================== #
    def _on_save(self) -> None:
        try:
            settings = self._collect_all()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            title="Save preset")
        if path:
            config_io.write_settings(path, settings)
            self._log_write(f"[saved preset → {path}]\n")

    def _on_load(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")], title="Load preset")
        if not path:
            return
        try:
            values = config_io.read_settings(path)
            self._apply_all(values)
            self._log_write(f"[loaded preset ← {path}]\n")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))

    def _on_reset(self) -> None:
        self._apply_all(self._defaults)
        self._log_write("[reset to defaults]\n")


def _open_external(path: str) -> None:
    try:
        if sys.platform.startswith("darwin"):
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as exc:  # pragma: no cover
        messagebox.showerror("Open failed", str(exc))
