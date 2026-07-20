"""
Keplerian planetary radial velocity
===================================
Line-of-sight radial velocity of a transiting planet, in the stellar rest
frame, valid for eccentric orbits.

The circular approximation ``K_p·sin(2π·φ)`` used elsewhere in the pipeline is
exact only for e = 0.  For an eccentric orbit both the amplitude and, more
importantly, the *shape* of the curve change: around the transit the offset
term ``e·cos ω_p`` and the modified slope dominate the error, which can reach
tens of km/s for well-known cases (GJ 3470 b, GJ 436 b, HAT-P-11 b).

Angle convention, matching `phase_scheduler.compute_transit_geometry`:
NEA ``pl_orblper`` is the argument of periastron of the *planet*, and Winn
(2010, arXiv:1001.2010) uses ``ω_star = ω_p + 180°``.  The transit occurs at
true anomaly ``ν_tr = π/2 − ω_star``, which anchors the time of periastron to
the transit ephemeris T0.

With that anchoring, ``planet_rv_kms`` reduces identically to
``K_p·sin(2π·φ)`` when e = 0, with the same sign as the rest of the pipeline
(redshift just after transit).
"""

from __future__ import annotations

import numpy as np

# Below this eccentricity the Keplerian and circular traces differ by far less
# than the resolution of a typical high-resolution spectrograph, so the
# pipeline keeps using the circular form.
ECC_MIN = 0.01

_KEPLER_TOL = 1e-12
_KEPLER_MAX_ITER = 60


def solve_kepler_E(M, ecc):
    """
    Solve Kepler's equation ``M = E − e·sin E`` for the eccentric anomaly.

    Newton-Raphson, vectorised over ``M``.  The starting guess is Danby's
    ``E0 = M + 0.85·e·sign(sin M)``, which converges for every eccentricity
    below 1 without the stalling that a bare ``E0 = M`` shows near periastron
    at high e.

    Parameters
    ----------
    M : array_like
        Mean anomaly [rad], any range.
    ecc : float
        Eccentricity, 0 <= e < 1.

    Returns
    -------
    ndarray
        Eccentric anomaly [rad].
    """
    ecc = float(ecc)
    if not 0.0 <= ecc < 1.0:
        raise ValueError(f"eccentricity out of range: {ecc}")

    M = np.mod(np.asarray(M, dtype=float), 2.0 * np.pi)
    if ecc == 0.0:
        return M

    E = M + 0.85 * ecc * np.sign(np.sin(M))
    for _ in range(_KEPLER_MAX_ITER):
        f = E - ecc * np.sin(E) - M
        E = E - f / (1.0 - ecc * np.cos(E))
        if np.all(np.abs(f) < _KEPLER_TOL):
            break
    else:
        raise RuntimeError(
            f"Kepler solver did not converge for e = {ecc} "
            f"(max residual {np.max(np.abs(f)):.3e})"
        )
    return E


def _true_from_eccentric(E, ecc):
    """True anomaly [rad] from eccentric anomaly."""
    return 2.0 * np.arctan2(
        np.sqrt(1.0 + ecc) * np.sin(0.5 * E),
        np.sqrt(1.0 - ecc) * np.cos(0.5 * E),
    )


def time_of_periastron(t0_bjd, period, ecc, omega_p_deg):
    """
    Time of periastron passage [same units as ``t0_bjd``], derived from the
    transit ephemeris.

    The transit happens at ``ν_tr = π/2 − ω_star`` with ``ω_star = ω_p + 180°``,
    so ``t_peri = T0 − P·M_tr/(2π)``.
    """
    omega_star = np.radians(float(omega_p_deg) + 180.0)
    nu_tr = 0.5 * np.pi - omega_star
    E_tr = 2.0 * np.arctan2(
        np.sqrt(1.0 - ecc) * np.sin(0.5 * nu_tr),
        np.sqrt(1.0 + ecc) * np.cos(0.5 * nu_tr),
    )
    M_tr = E_tr - ecc * np.sin(E_tr)
    return float(t0_bjd) - float(period) * M_tr / (2.0 * np.pi)


def true_anomaly(t_bjd, t0_bjd, period, ecc, omega_p_deg):
    """
    True anomaly [rad] of the planet at times ``t_bjd``, with the orbit
    anchored so that t = T0 is mid-transit.
    """
    t_peri = time_of_periastron(t0_bjd, period, ecc, omega_p_deg)
    M = 2.0 * np.pi * (np.asarray(t_bjd, dtype=float) - t_peri) / float(period)
    return _true_from_eccentric(solve_kepler_E(M, ecc), ecc)


def planet_rv_kms(t_bjd, t0_bjd, period, ecc, omega_p_deg, kp_kms):
    """
    Planetary radial velocity in the stellar rest frame [km/s].

        V_p(t) = K_p · [cos(ν(t) + ω_p) + e·cos ω_p]

    ``kp_kms`` must already carry the eccentricity correction
    (``K_p / sqrt(1 − e²)``, see `kp_eccentric`).  For e = 0 this returns
    ``K_p·sin(2π·φ)`` exactly.
    """
    ecc = float(ecc)
    omega_p = np.radians(float(omega_p_deg))
    nu = true_anomaly(t_bjd, t0_bjd, period, ecc, omega_p_deg)
    return float(kp_kms) * (np.cos(nu + omega_p) + ecc * np.cos(omega_p))


def kp_eccentric(kp_kms, ecc):
    """
    Planetary semi-amplitude corrected for eccentricity, ``K_p / sqrt(1−e²)``.

    Returns ``None`` when ``kp_kms`` is missing, and ``kp_kms`` unchanged for a
    circular orbit.
    """
    if kp_kms is None or not np.isfinite(kp_kms):
        return None
    ecc = float(ecc)
    if not 0.0 < ecc < 1.0:
        return float(kp_kms)
    return float(kp_kms) / np.sqrt(1.0 - ecc ** 2)


def omega_envelope(t_bjd, t0_bjd, period, ecc, kp_kms, n_omega=360):
    """
    Pointwise range of the planetary RV trace over all possible ω.

    Used when the catalogue gives an eccentricity but no argument of
    periastron: rather than silently picking a value, the pipeline shows how
    wide the prediction can be.

    Returns
    -------
    (v_lo, v_hi, omega_grid)
        ``v_lo``/``v_hi`` are arrays shaped like ``t_bjd``; ``omega_grid`` is
        the ω sampling in degrees.
    """
    omega_grid = np.linspace(0.0, 360.0, int(n_omega), endpoint=False)
    traces = np.array([
        planet_rv_kms(t_bjd, t0_bjd, period, ecc, w, kp_kms)
        for w in omega_grid
    ])
    return traces.min(axis=0), traces.max(axis=0), omega_grid


def _usable(x):
    return x is not None and np.isfinite(x)


def orbit_solution(t_bjd, t0_bjd, period, ecc, omega_p_deg, kp_kms,
                   n_omega=360):
    """
    Pick the orbital treatment for a target and evaluate every trace the plot
    needs.

    Three branches:

    ``circular``
        e missing or below `ECC_MIN`.  Identical to the pipeline's historical
        behaviour.
    ``keplerian``
        e and ω both known.  The adopted trace is the Keplerian one.
    ``envelope``
        e known, ω missing.  There is no preferred trace, so the adopted curve
        stays circular and the plot shows the band spanned by every possible
        ω around it.  This is what makes the size of the unknown visible
        rather than hidden behind an arbitrary default.

    Returns
    -------
    dict | None
        Keys ``mode``, ``v_adopted``, ``v_circ``, ``v_lo``, ``v_hi``,
        ``ecc``, ``omega_used``, ``kp_circ``, ``kp_ecc``, ``max_dev_circ``.
        ``None`` when K_p is unavailable, since nothing can be predicted then.
    """
    if not _usable(kp_kms):
        return None

    t_bjd = np.asarray(t_bjd, dtype=float)
    kp_circ = float(kp_kms)
    v_circ = kp_circ * np.sin(
        2.0 * np.pi * (t_bjd - float(t0_bjd)) / float(period)
    )

    # A catalogue value outside [0,1) is not a physical bound orbit; treat it
    # as unusable and keep scheduling rather than letting the Kepler solver's
    # ValueError abort the run.  `ecc_rejected` carries it into the log.
    ecc_val = float(ecc) if _usable(ecc) else 0.0
    ecc_rejected = None
    if not 0.0 <= ecc_val < 1.0:
        ecc_rejected, ecc_val = ecc_val, 0.0

    if ecc_val < ECC_MIN:
        return dict(
            mode="circular", v_adopted=v_circ, v_circ=v_circ,
            v_lo=None, v_hi=None, ecc=ecc_val, omega_used=None,
            kp_circ=kp_circ, kp_ecc=kp_circ, max_dev_circ=0.0,
            ecc_rejected=ecc_rejected,
        )

    kp_ecc = kp_eccentric(kp_circ, ecc_val)

    if _usable(omega_p_deg):
        omega = float(omega_p_deg)
        v_adopted = planet_rv_kms(t_bjd, t0_bjd, period, ecc_val, omega, kp_ecc)
        return dict(
            mode="keplerian", v_adopted=v_adopted, v_circ=v_circ,
            v_lo=None, v_hi=None, ecc=ecc_val, omega_used=omega,
            kp_circ=kp_circ, kp_ecc=kp_ecc,
            max_dev_circ=float(np.max(np.abs(v_adopted - v_circ))),
            ecc_rejected=None,
        )

    v_lo, v_hi, _ = omega_envelope(
        t_bjd, t0_bjd, period, ecc_val, kp_ecc, n_omega=n_omega,
    )
    return dict(
        mode="envelope", v_adopted=v_circ, v_circ=v_circ,
        v_lo=v_lo, v_hi=v_hi, ecc=ecc_val, omega_used=None,
        kp_circ=kp_circ, kp_ecc=kp_ecc,
        max_dev_circ=float(max(np.max(np.abs(v_lo - v_circ)),
                               np.max(np.abs(v_hi - v_circ)))),
        ecc_rejected=None,
    )


def describe_orbit_solution(sol) -> str:
    """One-line run-log summary of which orbital treatment was applied."""
    if sol is None:
        return "orbit: Kp unavailable, no planetary RV prediction"

    if sol["mode"] == "circular":
        if sol.get("ecc_rejected") is not None:
            return (
                f"orbit: catalogue e = {sol['ecc_rejected']} is out of range "
                f"[0,1) and was rejected; falling back to a circular orbit"
            )
        return f"orbit: circular (e = {sol['ecc']:.3f} < {ECC_MIN})"

    if sol["mode"] == "keplerian":
        return (
            f"orbit: keplerian, e = {sol['ecc']:.3f}, "
            f"omega_p = {sol['omega_used']:.1f} deg (NEA pl_orblper); "
            f"Kp {sol['kp_circ']:.2f} -> {sol['kp_ecc']:.2f} km/s; "
            f"max deviation from circular {sol['max_dev_circ']:.2f} km/s"
        )

    return (
        f"orbit: e = {sol['ecc']:.3f} but omega unavailable -> envelope over "
        f"[0,360) deg; Kp {sol['kp_circ']:.2f} -> {sol['kp_ecc']:.2f} km/s; "
        f"planetary RV anywhere in "
        f"[{np.min(sol['v_lo']):+.2f}, {np.max(sol['v_hi']):+.2f}] km/s; "
        f"worst-case deviation from circular {sol['max_dev_circ']:.2f} km/s"
    )
