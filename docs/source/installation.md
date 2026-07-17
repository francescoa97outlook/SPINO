# Installation

## Requirements

- **Python ≥ 3.9**
- **Tkinter** — part of the CPython standard library. If `import tkinter` fails:
  - Debian / Ubuntu: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - macOS (python.org / Homebrew builds include Tk); with pyenv you may need
    `brew install tcl-tk` and a matching Python build.
- Scientific stack (installed automatically): numpy, pandas, scipy, matplotlib,
  astropy, astroquery, pytz, seaborn, requests, PyYAML.

## Editable install (recommended for development)

```bash
cd SPINO
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

This installs the `spino` console entry point and all
dependencies, and includes the bundled data files
(`src/spino/data/`).

## Plain install

```bash
pip install .
```

## Run without installing

From a source checkout you can run directly if the dependencies are present:

```bash
pip install -r requirements.txt
python -m spino
```

## Verifying the install

A fast, GUI-free smoke test that exercises the whole pipeline:

```bash
# write a minimal settings.json (see docs/usage.md) then:
python -m spino.runner settings.json
```

You should see the pipeline log and, on success, PDFs/CSVs under the configured
`OUTPUT_DIR`.
