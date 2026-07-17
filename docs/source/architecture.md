# Architecture

## Package layout

```
src/spino/
├── app.py            # main window: builds the tabbed UI, wires orchestration
├── __main__.py       # `python -m spino`
├── config_io.py      # defaults (read from pipeline), help text, JSON (de)serialise
├── runner.py         # subprocess entry: overlay settings → run pipeline
├── theme.py          # colour palette + tab list (replaces GUIBRUSHR ConstantVariables)
├── panels/           # one class per config group + run_panel (log/output)
├── gui_toolkit/      # reused GUIBRUSHR widgets + theming (layout/, widget/, graphics.yaml)
├── pipeline/         # the scheduling pipeline (8 near-verbatim modules)
└── data/             # bundled catalogs (cat/), aux files (aux/), sky-transmission FITS
```

## Three layers

1. **GUI** (`app.py`, `panels/*`): a `MyTabPanel` notebook with one panel per
   config group. Each panel builds labelled `My*` widgets and exposes
   `collect()` (widgets → dict) and `set_values()` (dict → widgets). `app.py`
   merges all panels' `collect()` into a single flat settings dict.

2. **Runner** (`runner.py`): a headless subprocess entry point. It loads a
   `settings.json`, `setattr`s every key onto the pipeline's `phase_config`
   module, then imports and calls `phase_scheduler.main()`. Running the pipeline
   in a child process (rather than a thread) keeps the Tk UI responsive, isolates
   matplotlib's Agg backend, and guarantees a clean config each run.

3. **Pipeline** (`pipeline/*`): the scientific code, bundled almost verbatim
   from the original headless tool. It is driven entirely by module-level globals
   in `phase_config.py`.

## Data flow

```
 app.collect_all() ─► settings.json ─► subprocess: runner.py
                                             │  setattr onto phase_config
                                             ▼
                                    phase_scheduler.main()
                                             │  stdout
      run_panel log pane  ◄──────────────────┘
      run_panel output list  ◄── scans OUTPUT_DIR for *.pdf / *.csv
```

The Run panel launches the subprocess with `stdout`/`stderr` piped; a daemon
reader thread pushes lines onto a `queue.Queue`, and the Tk main loop drains the
queue via `after(150, …)` into the log widget (only the queue crosses the thread
boundary, so Tk stays single-threaded).

## Notes on the vendored code

- **gui_toolkit**: copied from GUIBRUSHR's `GUI/LAYOUT`, `GUI/WIDGET`, and
  `HelpButton`; the only edits were rewriting the `GUIBRUSHR....` import prefix to
  `spino.gui_toolkit....` and repointing `GraphicsConfig`'s YAML
  path to the co-located `graphics.yaml`. The matplotlib/PDF widgets were **not**
  copied (results open in the system viewer), so the toolkit needs only PyYAML.

- **pipeline**: flat imports (`from phase_config import …`) are preserved
  exactly as upstream; `runner.py` inserts `pipeline/` on `sys.path` so they
  resolve. The only pipeline edits: one import line, repointing the `phase_config`
  data paths at the bundled `data/` folder (with a user-writable default
  `OUTPUT_DIR`), and inlining three SI constants to drop a heavy petitRADTRANS
  dependency.
```
