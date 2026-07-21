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
    affiliation: "1"
affiliations:
  - name: "INAF, Osservatorio Astrofisico di Torino, via Osservatorio 20, 10025 Pino Torinese, Italy"
    index: 1
  - name: "Dipartimento di Fisica, Università degli Studi di Torino, via Pietro Giuria 1, I-10125 Torino, Italy"
    index: 2
date: 18 July 2026
bibliography: paper.bib
---

# Summary

**Airmass visibility, transit and secondary-eclipse phase prediction, and
telluric-overlap checking for exoplanet spectroscopy.**

`SPINO` (Software for exoPlanet vIsibility and Nightly Observations) is a
self-contained Tkinter desktop application that plans phase-coverage observations
of exoplanet transits and secondary eclipses, wrapping a scientific scheduling
pipeline behind an editable graphical interface: every parameter that would
otherwise live in a Python configuration file becomes a form field. Working from a
locally cached NASA Exoplanet Archive snapshot [@christiansen2025; @akeson2013]
(optionally refreshed online), SPINO filters candidates, computes per-planet
visibility for a given observatory and proposal window, ranks targets by the
Transmission and Emission Spectroscopy Metrics of @kempton2018, and produces, per
scheduled planet, event calendars, airmass plots, a one-page parameter summary
card, and an optional telluric-overlap diagram. Results are written as PDF and CSV
files, with a preselection table of the most promising recent targets. The
application runs offline out of the box thanks to bundled catalogue caches and
auxiliary data, and it also exposes a headless entry point for scripted use.

# Statement of need

Preparing ground-based spectroscopic proposals for exoplanet atmospheres requires
answering a recurring question: from a large catalogue, which planets have an
observable transit or secondary eclipse from a given site and window, and which are
worth the telescope time? Answering it normally means stitching together catalogue
queries, visibility calculations, transit-duration geometry [@winn2010], metric
rankings [@kempton2018], and, for high-resolution work [@birkby2018], a check that
the planetary signal is not buried under telluric lines, typically via ad hoc
scripts whose parameters are scattered across configuration files, error prone and
hard to share with students or collaborators.

`SPINO` turns that workflow into a single graphical tool. Every parameter is an
editable field, with built-in presets for common high-resolution instruments,
Neptunian-desert filtering following @castrogonzalez2024, and user-defined
criteria. A one-click run executes the pipeline in the background, streams its
log, and lists the generated outputs for inspection. Presets save and reload as
JSON, making a run reproducible and easy to hand over, lowering the barrier to
planning phase-resolved observations for observers and students preparing transit
and eclipse spectroscopy campaigns.

`SPINO` is intentionally a first-look, organizational aid rather than an
authoritative source: it turns a large, heterogeneous catalogue into a coherent
shortlist quickly, but every quantity it reports (ephemerides, visibility windows,
event durations, metrics) should still be checked independently for each target
before it is used in a proposal.

# State of the field

Several established tools address parts of the exoplanet observation-planning
problem: `astroplan` [@morris2018] computes target observability under
user-defined constraints; the Tapir package and its Swarthmore Transit Finder
[@jensen2013] predict transit/eclipse visibility for known planets and TESS
Objects of Interest [@ricker2015]; the NASA Exoplanet Archive Transit and
Ephemeris Service [@christiansen2025] does the same for a chosen observatory;
ExoClock [@kokori2023] and the Exoplanet Transit Database [@poddany2010] serve
precise ephemerides and community light curves. Each is a web service or
general-purpose library covering one piece of the workflow. SPINO instead
complements them by running locally from a cached catalogue snapshot and
combining candidate discovery, parameter retrieval, visibility,
spectroscopic-yield ranking, phase-coverage scheduling, and telluric-overlap
checking in one offline, reproducible, open-source pipeline, exposed through
both a GUI and a headless entry point, `python -m spino.runner settings.json`.

# Software design

SPINO separates a pure Python scheduling pipeline from a thin Tkinter presentation
layer, so the GUI and the headless runner share the same code path and a run is
fully described by one JSON preset. The pipeline runs in sequential stages
(catalogue loading/filtering, visibility and event-coverage computation, metric
ranking, figure/table generation), each logging progress to a stream the GUI
displays live. Catalogue access is cache-first: a bundled NASA Exoplanet Archive
snapshot works offline, and an optional refresh replaces the cache with a direct
download from the Archive. Missing stellar magnitudes are completed from SIMBAD
via Astroquery.

The telluric-overlap diagram computes the planetary radial-velocity excursion
during an event, including the barycentric contribution, against the telluric and
stellar rest frames (the quantity of interest for high-resolution
cross-correlation observations). It follows the full Keplerian radial-velocity
solution rather than the circular approximation $K_p\sin(2\pi\varphi)$, exact only
at $e=0$ and otherwise wrong by tens of km/s for catalogued eccentric orbits, e.g.
GJ 3470 b [@Bonfils2012; @Biddle2014; @Kosiarek2019], GJ 436 b [@Butler2004;
@Maciejewski2015; @Trifonov2018], HAT-P-11 b [@Bakos2010; @Stassun2017;
@Yee2018]. When eccentricity is catalogued but the argument of periastron is not,
SPINO does not assume a value: it plots the envelope over every possible argument
of periastron alongside the circular approximation, making the uncertainty
explicit rather than hiding it behind a default. A second panel plots the same
planet-minus-telluric radial-velocity difference against orbital phase across the
event, showing how the overlap evolves rather than only its extreme range.

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

SPINO grew out of the author's own work on ground-based high-resolution
spectroscopy of exoplanet atmospheres, replacing per-proposal ad hoc scripts with
a single reproducible configuration; its output has been shared informally with
colleagues. Because a run is captured in one JSON preset, a target shortlist can
be handed over, audited, and rerun exactly as produced, shortening the path from
catalogue to proposal draft and lowering the entry barrier for students
approaching this kind of planning.

# Figures

![The Run tab of the SPINO graphical interface, from which a scheduling run is
launched and its results collected. The remaining tabs (Catalog, Filters,
Observatory, Constraints, Custom Planets, Telluric, Output & Plot) hold the
configuration parameters, with save/reload of presets. During a run the pipeline
log streams in the central pane; afterward the two lower lists show the planets
that satisfied the constraints and, per planet, the files written. Reported
quantities are catalogue-derived and require independent verification.
](figures/gui.png)

![Example pipeline output for one scheduled target, WASP-83 b. Top left: target
altitude and airmass versus time for an observable transit, with the transit
highlighted and twilight bands shaded. Bottom left: the telluric-overlap diagram
for high-resolution spectroscopy, in two panels sharing the same
planet-minus-telluric radial velocity: the left panel shows the telluric and
stellar cross-correlation curves in the Earth frame with the planet's RV range
during the event; the right panel plots that RV difference against orbital phase,
showing how the overlap evolves rather than only its extreme range. WASP-83 b has
a catalogued eccentricity of 0.12 but no catalogued argument of periastron, so
both panels show the envelope over every possible argument of periastron alongside
the circular approximation, differing here by up to 16.7 km/s. Right: the one-page
summary card, with ephemerides drawn from the catalogue and, where available, from
the ExoClock project [@kokori2023]. Every quantity shown (ephemerides, visibility
windows, event durations, systemic and radial velocities, TSM and ESM) is
catalogue-derived and must be verified independently before use in a
proposal.](figures/output.png)

# AI usage disclosure

The scientific core of SPINO is code the author had written and used in earlier
work; the graphical layer reuses widget, panel, and theming modules from
GUIBRUSHR, an earlier toolkit by the same author. Generative AI tools (Claude,
Anthropic) were used to bring these pre-existing components together: connecting
the scheduling pipeline to the graphical layer, assisting with the interface
implementation, and providing language editing during manuscript preparation. The
scientific content, algorithms, and software design decisions are the author's
own work; the author reviewed, tested, and validated all AI-assisted code and
text.

# Acknowledgements

The graphical layer of SPINO is built on GUIBRUSHR
(<https://www.ict.inaf.it/gitlab/guibrushr/guibrushr>), an earlier toolkit by the
same author, whose widget, panel, and theming modules are bundled with the package
rather than declared as an external dependency; the reused components and their
license are documented in the repository. GUIBRUSHR is GPLv3, and SPINO, as a
derivative work, is distributed under the same terms (GPL-3.0-or-later).

This research has made use of the NASA Exoplanet Archive, operated by Caltech
under contract with NASA's Exoplanet Exploration Program [@christiansen2025;
@akeson2013]. The bundled catalogue is a snapshot of the Planetary Systems table
[@nea12], and the optional online refresh downloads directly from the Archive. It
has also used the SIMBAD database, operated at CDS, Strasbourg, France
[@wenger2000], queried through Astroquery [@astroquery2019] for stellar
magnitudes missing from the catalogue.

SPINO builds on the open-source scientific Python stack: Astropy [@astropy2022]
for coordinates, times, and visibility geometry; NumPy [@numpy2020] and SciPy
[@virtanen2020] for the metrics and telluric diagram; pandas [@pandas2010] for
catalogue handling; and Matplotlib [@matplotlib2007] with seaborn [@waskom2021]
for the figures.

# References