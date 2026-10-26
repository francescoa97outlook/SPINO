# Changelog

## 1.1.0

### Fixed

- The argument of periastron `pl_orblper` is read as ω★, that of the star's
  reflex orbit, with the transit at true anomaly π/2 − ω★ (Winn 2010); the
  planetary radial velocity uses ω_p = ω★ + 180°. Version 1.0.3 read it as ω_p,
  which placed the eclipses of eccentric orbits on the wrong side of mid-orbit.
- Time systems of the mid-transit time: a bare `JD` label is read as BJD_TDB
  (the archive applies it to epochs that are already BJD_TDB), and only an
  explicit `JD-UTC` is converted from geocentric UTC. `BJD-UTC`, `BJD-TCB` and
  `HJD-TDB` are now converted; `BJD-TT` and `BJD-TBD` are read as BJD_TDB.
- Events on orbits shorter than the night: each orbit is matched on its own,
  so two partial transits on one night are two events with their own
  coverage, never one event with the summed coverage. Night plots and
  telluric pages follow the orbit of their own event.
- A `pl_tranmid` entered in `CUSTOM_PLANETS` is read as BJD_TDB and no longer
  inherits the time system of the catalogue row it replaces.
- The telluric radial-velocity grid is built in whole steps from `start` and
  never extends beyond `stop`.

### Changed

- Default telluric radial-velocity grid `(-50, 50, 1)`: 101 points, 0
  included (was `(-50, 50, 1.5)`, which reached +50.5 and skipped 0).
- Eccentricity and argument of periastron are composed together from the most
  recent reference that reports an eccentricity; a measured planetary mass is
  preferred to a more recent upper limit.
- The night-plot footer reads `rule off` instead of `OK` when the Moon rule is
  switched off (`moon_dist_factor = 0`).
- Summary card: the ephemeris reference sits inside the header bar, and the
  footer reads "SPINO: Planet Parameter Summary".
- Help texts and configuration comments state how custom planets interact
  with the filters, what the Moon rule does, and the twilight values of
  `max_sun_alt`.
- Bundled catalogue snapshots refreshed (2026-10-01), with the limit-flag
  columns.

### Added

- Limit flags of the archive (`pl_orbeccenlim`, `pl_orblperlim`,
  `pl_bmasselim`): eccentricity upper limits are treated as circular and
  flagged `ecc_upper_limit`, or adopted as values with `USE_ECC_UPPER_LIMITS`;
  mass upper limits are shown as such, with the TSM as a lower limit.
- Systemic velocity from Gaia DR3 or SIMBAD, whichever quotes the smaller
  uncertainty, when the archive has none; the source is printed on the
  summary card and on the telluric page.
- Telluric page for pre- and post-eclipse events over the whole emission
  window, from quadrature to eclipse contact, with the part observable on the
  night hatched.
- `CHANGELOG.md`.
