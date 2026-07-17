# -*- coding: utf-8 -*-
#
# SPINO documentation build configuration file.
#
# This file is executed with the current directory set to its containing dir.

import os
os.environ['SPHINX_BUILD'] = '1'

import re
import sys
from datetime import date

import matplotlib
matplotlib.use('Agg')  # headless backend before any pipeline module imports pyplot

# Project root is two levels up from docs/source/.
project_root = os.path.abspath('../../')

# Make the package importable for autodoc (repo_root/src). The pipeline modules
# import their siblings by bare name (the runner puts this dir on sys.path at
# runtime); mirror that here so autodoc can import them.
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, os.path.join(project_root, 'src', 'spino', 'pipeline'))

# The version is read from the single source of truth (spino.__version__,
# defined in src/spino/__init__.py). 'unknown' is only used if the package
# cannot be imported at all.
version_str = 'unknown'
try:
    import spino
    version_str = getattr(spino, '__version__', version_str)
except ImportError:
    version_str = 'unknown'

# -- General configuration ------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints',
    'sphinx_copybutton',
    'myst_parser',
]

templates_path = ['_templates']

# Source filename suffixes: reStructuredText for the index/apidoc pages, and
# Markdown (via MyST) for the hand-written guides.
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

master_doc = 'index'

project = 'SPINO'
copyright = f'2025-{date.today().year:d}, Francesco Amadori'
author = 'Francesco Amadori'

# The short X.Y version and the full version.
version = re.search(r'([\.\d]*)', version_str).group(0)
release = version_str

language = 'en'

exclude_patterns = ['_build', '.DS_Store', '**.ipynb_checkpoints']

pygments_style = 'sphinx'

# -- MyST (Markdown) ------------------------------------------------------

# Note: 'linkify' (auto-linking of bare URLs) is intentionally omitted because it
# needs the optional 'linkify-it-py' package. The docs use explicit links, so add
# it back here (and 'linkify-it-py' to docs/requirements.txt) only if you want it.
myst_enable_extensions = [
    'colon_fence',
    'deflist',
]
myst_heading_anchors = 3

# -- Options for autodoc --------------------------------------------------

autodoc_mock_imports = []

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'undoc-members': True,
    'show-inheritance': True,
    'exclude-members': '__weakref__',
}
autodoc_typehints = 'description'

# -- Options for napoleon -------------------------------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_ivar = True

# -- intersphinx ----------------------------------------------------------

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
    'astropy': ('https://docs.astropy.org/en/stable/', None),
}

# -- Options for HTML output ----------------------------------------------

html_theme = 'furo'
html_title = 'SPINO'

html_theme_options = {
    "sidebar_hide_name": False,
    "light_css_variables": {
        "color-background-border": "#d0d0d0",
    },
}

html_logo = '_static/spino_logo.png'
html_favicon = '_static/favicon.ico'

html_static_path = ['_static']
html_css_files = ["custom.css"]

html_show_copyright = True
htmlhelp_basename = 'SPINOdoc'

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '10pt',
}

latex_documents = [
    (
        master_doc,
        'SPINO.tex',
        'SPINO Documentation',
        'Francesco Amadori',
        'howto',
    ),
]
