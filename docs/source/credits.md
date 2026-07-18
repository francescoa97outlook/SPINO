# Credits & licensing

## GUI toolkit (GUIBRUSHR)

The GUI widget, panel, and theming classes under
`src/spino/gui_toolkit/` are reused from
[**GUIBRUSHR**](https://www.ict.inaf.it/gitlab/guibrushr/guibrushr), an earlier
toolkit written by the same author as SPINO (Francesco Amadori)
(`MyPanel`, `MyTabPanel`, `ScaleManager`, `GraphicsConfig`, `MyLabel`,
`MyButton`, `MyEntry`, `MyTextField`, `MyDropDown`, `MyCheckBox`, `MyTable`,
`HelpButton`, and `graphics.yaml`). They were copied and adapted (import prefix
rewritten, YAML path repointed) rather than rewritten.

**GUIBRUSHR is licensed under the GNU General Public License v3.0.** Because this
application incorporates that code, it is a *derivative work* and is therefore
also distributed under the **GPL-3.0-or-later** (see the top-level `LICENSE`).
If you intend to publish this project under a different license, you must first
replace the vendored GUIBRUSHR widgets with an independent implementation.

## Scientific pipeline

The scheduling pipeline under `src/spino/pipeline/` implements,
among others:

- TSM / ESM metrics following **Kempton et al. (2018)**;
- the Neptunian-desert KDE contour from **Castro-González et al. (2024)**;
- transit-duration estimates via the **Winn (2010)** formula;
- catalog data from the **NASA Exoplanet Archive** (Planetary Systems table).

Please cite the relevant works when using results produced by this tool.

## Bundled data

- `data/cat/PS_latest_*.csv`: NASA Exoplanet Archive Planetary Systems cache.
- `data/auxiliary/desert_boundaries.txt`, `data/auxiliary/kde_points_NEA.npz`: desert
  polygon and KDE background.
- `data/sky_transmission.fits`: GIANO-B sky-transmission spectrum used by the
  optional telluric-overlap page.
