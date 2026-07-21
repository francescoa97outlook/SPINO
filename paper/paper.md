---
title: "SPINO: Software for exoPlanet vIsibility and Nightly Observations"
tags:
  - Python
  - astronomy
  - exoplanets
  - transits
  - observation scheduling
  - Tkinter
authors:
  - name: Francesco Amadori
    orcid: 0000-0003-1316-1033
    affiliation: "1, 2"
  - name: Paolo Giacobbe
    orcid: 0000-0001-7034-7024
    affiliation: "1"
  - name: Matteo Brogi
    orcid: 0000-0002-7704-0153
    affiliation: "2, 1"
  - name: Ilaria Carleo
    orcid: 0000-0002-0810-3747
    affiliation: "1, 3"
affiliations:
  - name: "INAF, Osservatorio Astrofisico di Torino, via Osservatorio 20, 10025 Pino Torinese, Italy"
    index: 1
  - name: "Dipartimento di Fisica, Università degli Studi di Torino, via Pietro Giuria 1, I-10125 Torino, Italy"
    index: 2
  - name: "Instituto de Astrofísica de Canarias (IAC), E-38205 La Laguna, Tenerife, Spain"
    index: 3
date: 18 July 2026
bibliography: paper.bib
---

# Summary

**Airmass visibility, transit and secondary-eclipse phase prediction, and
telluric-overlap checking for exoplanet spectroscopy.**

`SPINO` (Software for exoPlanet vIsibility and Nightly Observations) is a
self-contained desktop application that plans phase-coverage observations of
exoplanet transits and secondary eclipses. It wraps a scientific scheduling
pipeline behind an editable graphical interface built with Tkinter, so every
parameter that would otherwise live in a Python configuration file becomes a form
field. SPINO works from a locally cached copy of the NASA Exoplanet Archive
[@christiansen2025; @akeson2013], which can optionally be refreshed online. From
that catalogue it filters candidates, computes per-planet visibility for a given
observatory and proposal window, ranks targets by the Transmission and Emission
Spectroscopy Metrics of @kempton2018, and produces, for each scheduled planet,
night-by-night event calendars, airmass plots, a one-page parameter summary card,
and an optional telluric-overlap diagram. Results are written as PDF and CSV files,
and a preselection table lists the most promising recent targets. The application
runs offline out of the box thanks to bundled catalogue caches and auxiliary data,
and it also exposes a headless entry point for scripted or batch use.

# Statement of need

Preparing ground-based spectroscopic proposals for exoplanet atmospheres requires
answering a recurring, tedious question: from a large catalogue, which planets have
an observable transit or secondary eclipse from a specific site during a specific
window, and which of those are worth the telescope time? Answering it normally means
stitching together catalogue queries, visibility calculations, transit-duration
geometry [@winn2010], metric rankings [@kempton2018], and, for high-resolution work
[@birkby2018], a check that the planetary signal is not buried under telluric lines.
In practice this lives in ad hoc scripts whose parameters are scattered across
configuration files, which is error prone and hard to share with students or
collaborators.

`SPINO` turns that workflow into a single graphical tool. Every configuration
parameter is an editable field, with built-in presets for common high-resolution
instruments: catalogue source, observatory, proposal window, observing and
event-coverage constraints, hand-entered targets, and output options. The filters
include Neptunian-desert selections that follow the exo-Neptunian landscape
described by @castrogonzalez2024, together with user-defined criteria. A one-click
run executes the pipeline in a background process, streams its log, and lists the
generated figures and tables for inspection. Presets can be saved and reloaded as
JSON, making a scheduling run reproducible and easy to hand over. By combining
catalogue handling, visibility, event-coverage constraints, spectroscopic-metric
ranking, and telluric-overlap checking in one reproducible, offline-capable
interface, SPINO lowers the barrier to planning phase-resolved observations and is
aimed at observers and students preparing transit and eclipse spectroscopy
campaigns.

`SPINO` is intentionally a first-look, organizational aid rather than an
authoritative source. Its purpose is to turn a large, heterogeneous catalogue into a
coherent, homogeneous shortlist of candidates with consistent visibility, ranking,
and telluric information, so that a proposal can be assembled quickly. It is not a
final tool: every quantity it reports (ephemerides, visibility windows, event
durations, and metrics) should be checked independently and carefully for each target
before it is used in a proposal. SPINO does not remove the need for those per-target
verifications; it is meant to make them faster to organize.

# State of the field

Several established tools address parts of the exoplanet observation-planning
problem, and SPINO is designed to complement rather than replace them. The
`astroplan` package [@morris2018] is the reference Python library for computing
rise, set, and meridian transit times and for checking target observability under
user constraints. It is a general-purpose toolkit rather than an exoplanet
phase-coverage planner, so on its own it does not rank targets by spectroscopic
yield or build event calendars around a proposal window. The Tapir package and its
Swarthmore Transit Finder web interface [@jensen2013] compute transit and eclipse
observability for known planets and TESS Objects of Interest [@ricker2015] and
produce airmass plots and finding charts, but they operate as a web service tied to
online ephemeris sources rather than as a scriptable local application. The NASA
Exoplanet Archive Transit and Ephemeris Service [@christiansen2025] predicts when
transits and phase quadratures occur and whether they are visible from a chosen
observatory, again through a web interface. The ExoClock project [@kokori2023]
maintains precise, homogeneous ephemerides and is a data source for event timing
rather than a planning application. The Exoplanet Transit Database [@poddany2010]
provides transit predictions and community light curves through a web portal.

SPINO occupies a distinct niche: it runs locally from a cached catalogue snapshot,
so it works offline and is reproducible for a fixed snapshot; it integrates
candidate filtering, spectroscopic-yield ranking, phase-coverage scheduling for
transits and secondary eclipses, and telluric-overlap visualization aimed at
high-resolution spectroscopy in one open-source desktop application; and it exposes
the same pipeline both through a GUI and through a headless entry point,
`python -m spino.runner settings.json`, for scripted use.

# Software design

SPINO separates a pure Python scheduling pipeline from a thin Tkinter presentation
layer, so the same code path serves both the GUI and the headless runner and a run
is fully described by a single JSON preset. The pipeline is organized in sequential
stages (catalogue loading and filtering, visibility and event-coverage computation,
metric ranking, and figure and table generation), each of which logs its progress to
a stream that the GUI displays live. Catalogue access is cache-first: a bundled NASA
Exoplanet Archive snapshot makes the tool usable offline, and an optional refresh
replaces the cache with a direct download from the Archive. Stellar magnitudes
missing from the catalogue are completed from SIMBAD through Astroquery. The
telluric-overlap diagram computes the planetary radial-velocity excursion during an
event, including the barycentric contribution, against the telluric and stellar rest
frames, which is the quantity of interest when assessing high-resolution
cross-correlation observations. That excursion follows the full Keplerian
radial-velocity solution rather than the circular approximation
$K_p\sin(2\pi\varphi)$, which is exact only in the $e=0$ limit 
and for a catalogued eccentric orbit can be wrong by tens of km/s, 
e.g. GJ 3470 b [@Bonfils2012; @Biddle2014; @Kosiarek2019],
GJ 436 b [@Butler2004; @Maciejewski2015; @Trifonov2018],
HAT-P-11 b [@Bakos2010; @Stassun2017; @Yee2018].
When the orbital eccentricity is catalogued but the argument of periastron is not,
SPINO does not assume a value for it; instead it plots the envelope spanned by every
possible argument of periastron, alongside the circular approximation for reference,
so the diagram shows the size of that uncertainty rather than hiding it behind an
arbitrary default. A second panel of the same diagram plots this planet-minus-telluric
radial-velocity difference against orbital phase across the whole event, so how the
overlap evolves during the observation is visible, not only its extreme range.

# Features

- Every pipeline parameter is editable in the GUI, with instrument presets and
  save/load of JSON presets.
- Catalogue loading from a bundled NASA Exoplanet Archive cache (NEA/TESS), with an
  optional online refresh.
- Neptunian-desert and user-defined filtering, per-planet visibility, and
  event-coverage constraints for transits and for the phase windows before and after
  secondary eclipse.
- Target ranking by the Transmission and Emission Spectroscopy Metrics.
- Per-planet outputs: summary card, event calendars, airmass plots, and an optional
  telluric-overlap diagram, plus a period-radius desert landscape and a preselection
  table.
- Keplerian, not circular, planetary radial-velocity prediction for eccentric orbits,
  with an explicit uncertainty envelope when the argument of periastron is unknown.
- A headless entry point, `python -m spino.runner settings.json`, which runs the same
  pipeline from a saved preset for scripted use.

# Research impact statement

SPINO grew out of the author's own work on ground-based high-resolution spectroscopy
of exoplanet atmospheres, where it replaced a collection of per-proposal ad hoc
scripts with a single reproducible configuration, and its output has been shared
informally with colleagues. Because a scheduling run is captured in one JSON preset,
a target shortlist can be handed over, audited, and rerun exactly as produced, which
is what makes the tool useful beyond a single user: it shortens the path from
catalogue to proposal draft for transit and eclipse spectroscopy campaigns, and it
lowers the entry barrier for students approaching this kind of planning.

# Figures

![The Run tab of the SPINO graphical interface, from which a scheduling run is
launched and where its results are collected. The remaining tabs (Catalog, Filters,
Observatory, Constraints, Custom Planets, Telluric, Output & Plot) hold the
configuration parameters, and presets can be saved and reloaded here. During a run the
pipeline log is streamed in the central pane; at the end of the run the two lower lists
show the planets that satisfied the constraints and, for the selected planet, the files
that were written. The quantities reported in the log and in those files are catalogue
derived and require independent verification.](figures/gui.png)

![Example pipeline output for a single scheduled target, WASP-83 b. Top left: target
altitude and airmass versus time for one observable transit, with the transit itself
highlighted along the trajectory and the twilight bands shaded. Bottom left: the
telluric-overlap diagram used for high-resolution spectroscopy, in two panels sharing
the same planet-minus-telluric radial velocity. The left panel shows the telluric and
stellar cross-correlation curves in the Earth frame together with the range of
radial velocities the planet sweeps through during the event; the right panel plots
that same radial-velocity difference against orbital phase across the event, showing
how the overlap evolves rather than only its extreme range. WASP-83 b has a catalogued
eccentricity of 0.12 but no catalogued argument of periastron, so both panels show the
envelope spanned by every possible argument of periastron alongside the circular
approximation, making explicit that the two differ here by up to 16.7 km/s. Right: the
one-page parameter summary card for the target, whose ephemerides are drawn from the
catalogue and, where available, from the ExoClock project [@kokori2023]. Every quantity
shown here (ephemerides, visibility windows, event durations, systemic and radial
velocities, and the TSM and ESM metrics) is derived from the input catalogue and must
be verified independently for each target before it is used in a
proposal.](figures/output.png)

# AI usage disclosure

The scientific core of SPINO is assembled from code that the author had written and
used in earlier work, and the graphical layer reuses widget, panel, and theming
modules from GUIBRUSHR, an earlier toolkit by the same author. Generative AI tools
(Claude, Anthropic) were used to bring these pre-existing components together into a
single application: connecting the scheduling pipeline to the graphical layer, and
assisting with the implementation of the interface itself. AI tools were also used
for language editing during the preparation of this manuscript. The scientific
content, the algorithms, and the software design decisions are the work of the
author, who reviewed, tested, and validated all AI-assisted code and text.

# Acknowledgements

The graphical layer of SPINO is built on GUIBRUSHR
(<https://www.ict.inaf.it/gitlab/guibrushr/guibrushr>), an earlier toolkit by the same
author, whose widget, panel, and theming modules are bundled with the package rather
than declared as an external dependency; the reused components and their license are
documented in the repository. GUIBRUSHR is released under the GNU General Public
License v3, and SPINO, as a derivative work, is distributed under the same terms
(GPL-3.0-or-later).

This research has made use of the NASA Exoplanet Archive, which is operated by the
California Institute of Technology, under contract with the National Aeronautics and
Space Administration under the Exoplanet Exploration Program
[@christiansen2025; @akeson2013]. The bundled catalogue is a snapshot of the
Planetary Systems table [@nea12]; the access date of the snapshot is
recorded in the repository, and the optional online refresh is a direct download
from the Archive. This research has also made use of the SIMBAD database, operated
at CDS, Strasbourg, France [@wenger2000], queried through Astroquery
[@astroquery2019] to retrieve stellar magnitudes when they are missing from the
catalogue.

SPINO builds on the open-source scientific Python stack: Astropy [@astropy2022] for
coordinates, times, and visibility geometry, NumPy [@numpy2020] and SciPy
[@virtanen2020] for the numerical work behind the metrics and the telluric diagram,
pandas [@pandas2010] for catalogue handling, and Matplotlib [@matplotlib2007] with
seaborn [@waskom2021] for the figures.

# References