<p align="center">
  <img src="assets/spino_logo.png" alt="SPINO logo" width="240">
</p>

<h1 align="center">SPINO</h1>
<p align="center"><em>Software for exoPlanet vIsibility and Nightly Observations</em></p>

<p align="center">
  <a href="https://github.com/francescoa97outlook/SPINO"><img src="https://img.shields.io/badge/GitHub-SPINO-181717.svg?logo=github" alt="Source on GitHub"></a>
  <a href="https://www.gnu.org/licenses/gpl-3.0"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3"></a>
  <a href="https://spino.readthedocs.io/en/latest/?badge=latest"><img src="https://readthedocs.org/projects/spino/badge/?version=latest" alt="Documentation Status"></a>
  <a href="https://pypi.org/project/spino/"><img src="https://img.shields.io/pypi/v/spino.svg" alt="PyPI version"></a>
</p>

---

## Overview

**SPINO** is a self-contained **Tkinter** desktop application for planning
exoplanet **transit / secondary-eclipse phase-coverage** observations. It wraps a
scientific scheduling pipeline (catalog loading, desert filtering, per-planet
visibility, TSM/ESM ranking, telluric-overlap plots) behind an editable graphical
interface. Every parameter that used to live in a Python config file is now a
form field.

The widget/panel/theming layer is reused from the
[GUIBRUSHR](https://www.ict.inaf.it/gitlab/guibrushr/guibrushr) project; the
scheduling pipeline is bundled in `src/spino/pipeline/`. **The whole thing is
standalone**: all Python modules and data files it needs are vendored into the
package, so it runs offline out of the box.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Documentation](#documentation)
- [Architecture](#architecture-at-a-glance)
- [Troubleshooting](#troubleshooting)
- [Support](#support)
- [License &amp; Attribution](#license--attribution)
- [Citation](#citation)
- [Acknowledgments](#acknowledgments)

---

## Features

- **Every config parameter is editable in the GUI**: catalog source, desert /
  extra filters, observatory (telescope + instrument + site), proposal window,
  observing & event-coverage constraints, hand-entered custom planets, the
  telluric-overlap plot grid, and all output / landscape settings.
- **One-click run** of the pipeline in a background subprocess, with the live
  log streamed into the window and a **Stop** button.
- **Generated PDFs / CSVs listed** in the app; double-click to open them in your
  system viewer.
- **Save / Load presets** as JSON, and **Reset to defaults**.
- Bundled NASA Exoplanet Archive catalog cache, desert-boundary / KDE aux files,
  and a sky-transmission FITS, so it runs offline out of the box.

---

## Prerequisites

- **Python 3.10+**
- **Tkinter** ships with most Python builds (including the conda-forge Python).
  There is no `tkinter` package on PyPI, so `pip install tkinter` does not work;
  if `import tkinter` fails, install it with your package manager:

  ```bash
  conda install tk                 # conda
  sudo apt install python3-tk      # Debian / Ubuntu
  sudo dnf install python3-tkinter # Fedora
  ```

---

## Installation

### Option A: Install with conda (recommended)

The conda-forge Python 3.10 already bundles Tkinter, so nothing extra is needed:

```bash
conda create -n spino_env python=3.10
conda activate spino_env
pip install spino
```

### Option B: Install from PyPI into an existing environment

```bash
pip install spino
```

### Option C: Clone and install in editable mode (for development)

```bash
git clone https://github.com/francescoa97outlook/SPINO
cd SPINO
python -m venv .venv && source .venv/bin/activate   # or a conda env
pip install -e .
```

This installs the `spino` console entry point and all Python dependencies.

---

## Usage

### Launch the GUI

```bash
spino                # console entry point (after pip install)
# or, from a source checkout:
python -m spino
```

### Headless run (quickest smoke test, no GUI)

```bash
python -m spino.runner path/to/settings.json
```

---

## Documentation

Full documentation is hosted on **Read the Docs**:
[spino.readthedocs.io](https://spino.readthedocs.io).

The sources live in `docs/source/`:

| Doc | Contents |
|---|---|
| [installation.md](docs/source/installation.md) | Requirements, venv, `python3-tk`, editable install |
| [usage.md](docs/source/usage.md) | Tab-by-tab walkthrough, running, presets, outputs |
| [configuration.md](docs/source/configuration.md) | Reference for every configuration parameter |
| [architecture.md](docs/source/architecture.md) | How the GUI, runner subprocess and pipeline fit together |
| [credits.md](docs/source/credits.md) | GUIBRUSHR reuse and licensing |

To build the documentation locally:

```bash
./build_docs.sh
# then open docs/build/html/index.html
```

---

## Architecture (at a glance)

```
GUI (app.py + panels/)  --collect-->  settings.json
        |                                   |
        |  subprocess: python -m spino.runner settings.json
        v                                   v
   log pane  <--stdout--  runner.py  --overlay-->  pipeline/phase_config
                                |                          |
                                +---> pipeline/phase_scheduler.main()
                                              |
                                        OUTPUT_DIR/*.pdf, *.csv
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'tkinter'`**

- Tkinter is not bundled on some Linux Python builds. Install it with
  `sudo apt install python3-tk` (Debian/Ubuntu) or the equivalent for your
  distribution.

**Import errors after installation**

```bash
pip install -e . --force-reinstall
```

**The GUI opens but the catalog is empty**

- SPINO ships with a cached NASA Exoplanet Archive catalog. If you switched the
  catalog source, ensure network access or revert to the bundled cache.

---

## Support

For questions, bug reports, or technical assistance, please open an issue on the
[GitHub repository](https://github.com/francescoa97outlook/SPINO/issues) or
contact:

**Francesco Amadori**
📧 [francesco.a97.ing@outlook.it](mailto:francesco.a97.ing@outlook.it)

---

## License & Attribution

SPINO is free software: you can redistribute it and/or modify it under the terms
of the **GNU General Public License v3.0 or later** (see [LICENSE](LICENSE)).

It reuses GUI widget code from **GUIBRUSHR**, which is GPLv3; as a derivative work
SPINO is therefore also GPLv3. See
[docs/source/credits.md](docs/source/credits.md) and the
[GUIBRUSHR project](https://www.ict.inaf.it/gitlab/guibrushr/guibrushr).

---

## Citation

If you use SPINO in your research, please cite this repository:
[github.com/francescoa97outlook/SPINO](https://github.com/francescoa97outlook/SPINO).

---

## Acknowledgments

SPINO relies on several open-source packages, including
[NumPy](https://numpy.org), [SciPy](https://scipy.org),
[Matplotlib](https://matplotlib.org), [pandas](https://pandas.pydata.org),
[Astropy](https://www.astropy.org), and
[astroquery](https://astroquery.readthedocs.io), and reuses the GUI toolkit from
[GUIBRUSHR](https://www.ict.inaf.it/gitlab/guibrushr/guibrushr).
