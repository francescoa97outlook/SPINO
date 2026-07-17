"""
Scale Height Calculator for Exoplanet Atmospheres
==================================================
Computes the atmospheric scale height:

    H = k_B * T_eq / (mu * g)

where g = G * M_p / R_p^2 and mu is the mean molecular weight per molecule.

Usage
-----
Either supply a composition dict (VMR + molecular masses) to have the MMW
computed automatically, or pass a numeric ``mu`` directly:

    # Option A – composition dict
    result = compute_scale_height(
        M_planet=0.096, R_planet=0.98, T_eq=525,
        species={
            'H2': {'vmr': 0.836835, 'M': 2.016},
            'He': {'vmr': 0.141943, 'M': 4.003},
        },
        M_unit='Mjup', R_unit='Rjup',
    )

    # Option B – direct MMW
    result = compute_scale_height(
        M_planet=10.5, R_planet=3.2, T_eq=900,
        mu=2.3,
        M_unit='Mearth', R_unit='Rearth',
    )

    print(result['H_km'], 'km')
"""

import numpy as np

# ── Physical constants ─────────────────────────────────────────────────────────
_M_JUP   = 1.89813e27    # kg
_R_JUP   = 6.99110e7     # m
_M_EARTH = 5.97219e24    # kg
_R_EARTH = 6.37100e6     # m
_G       = 6.67430e-11   # m³ kg⁻¹ s⁻²
_K_B     = 1.380649e-23  # J K⁻¹
_N_A     = 6.02214076e23 # mol⁻¹


# ── Public helpers ─────────────────────────────────────────────────────────────

def mean_molecular_weight(species: dict) -> float:
    """
    Compute the mean molecular weight from a species composition dict.

    Parameters
    ----------
    species : dict
        {name: {'vmr': float, 'M': float [g/mol]}, ...}
        VMRs do not need to be normalised; they are used as relative weights.

    Returns
    -------
    mu : float
        Mean molecular weight [g/mol].

    Raises
    ------
    ValueError
        If no species are provided or all VMRs sum to zero.
    """
    if not species:
        raise ValueError("'species' dict is empty.")

    total_vmr = sum(d['vmr'] for d in species.values())
    if total_vmr <= 0:
        raise ValueError("Sum of VMRs must be positive.")

    mu = sum(d['vmr'] * d['M'] for d in species.values()) / total_vmr
    return float(mu)


def compute_scale_height(
    M_planet: float,
    R_planet: float,
    T_eq: float,
    *,
    species: dict | None = None,
    mu: float | None = None,
    M_unit: str = 'Mjup',
    R_unit: str = 'Rjup',
) -> dict:
    """
    Compute the atmospheric scale height for an exoplanet.

    Parameters
    ----------
    M_planet : float
        Planet mass, in the unit given by *M_unit*.
    R_planet : float
        Planet radius, in the unit given by *R_unit*.
    T_eq : float
        Equilibrium temperature [K].
    species : dict, optional
        Atmospheric composition: {name: {'vmr': float, 'M': float [g/mol]}}.
        Used to compute the MMW when *mu* is not supplied.
    mu : float, optional
        Mean molecular weight [g/mol].  Takes precedence over *species* if
        both are given.
    M_unit : str
        Mass unit: ``'Mjup'`` (default) or ``'Mearth'``.
    R_unit : str
        Radius unit: ``'Rjup'`` (default) or ``'Rearth'``.

    Returns
    -------
    dict with keys
        H_m       : float – scale height [m]
        H_km      : float – scale height [km]
        g         : float – surface gravity [m s⁻²]
        g_cgs     : float – surface gravity [cm s⁻²]
        mu        : float – mean molecular weight [g mol⁻¹]
        mu_method : str   – ``'direct'`` or ``'composition'``
        T_eq      : float – equilibrium temperature used [K]

    Raises
    ------
    ValueError
        If neither *mu* nor *species* is given, or if unit strings are invalid,
        or if mass/radius/temperature are non-positive.
    """
    # ── Validate inputs ────────────────────────────────────────────────────────
    for name, val in [('M_planet', M_planet), ('R_planet', R_planet),
                      ('T_eq', T_eq)]:
        if not np.isfinite(val) or val <= 0:
            raise ValueError(f"{name} must be finite and positive (got {val}).")

    # ── Unit conversions ───────────────────────────────────────────────────────
    _M_UNITS = {'Mjup': _M_JUP, 'Mearth': _M_EARTH}
    _R_UNITS = {'Rjup': _R_JUP, 'Rearth': _R_EARTH}

    if M_unit not in _M_UNITS:
        raise ValueError(f"Unknown M_unit {M_unit!r}. Choose 'Mjup' or 'Mearth'.")
    if R_unit not in _R_UNITS:
        raise ValueError(f"Unknown R_unit {R_unit!r}. Choose 'Rjup' or 'Rearth'.")

    M_p = M_planet * _M_UNITS[M_unit]   # kg
    R_p = R_planet * _R_UNITS[R_unit]   # m

    # ── Surface gravity ────────────────────────────────────────────────────────
    g = _G * M_p / R_p**2               # m s⁻²

    # ── Mean molecular weight ──────────────────────────────────────────────────
    if mu is not None:
        mu_val     = float(mu)
        mu_method  = 'direct'
    elif species is not None:
        mu_val     = mean_molecular_weight(species)
        mu_method  = 'composition'
    else:
        raise ValueError("Provide either 'mu' (float) or 'species' (dict).")

    if mu_val <= 0:
        raise ValueError(f"mu must be positive (got {mu_val}).")

    # ── Scale height ───────────────────────────────────────────────────────────
    mu_kg  = mu_val * 1e-3 / _N_A      # kg per molecule
    H      = _K_B * T_eq / (mu_kg * g) # m

    return {
        'H_m':       H,
        'H_km':      H / 1e3,
        'g':         g,
        'g_cgs':     g * 100.0,
        'mu':        mu_val,
        'mu_method': mu_method,
        'T_eq':      T_eq,
    }


# ── Standalone demo ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # ── INITIAL DATA (edit here) ───────────────────────────────────────────────
    M_planet = 0.096   # M_Jup
    R_planet = 0.98    # R_Jup
    T_eq     = 525     # K

    # Option A: species composition dict  → MMW computed automatically
    SPECIES = {
        'H2':  {'vmr': 0.836835,         'M': 2.016},
        'He':  {'vmr': 0.141943,         'M': 4.003},
        'H2O': {'vmr': 0.01120,          'M': 18.015},
        'CO':  {'vmr': 0.009985,         'M': 28.010},
        'CO2': {'vmr': 0.000028246,      'M': 44.009},
        'NH3': {'vmr': 0.0000074088,     'M': 17.031},
        'CH4': {'vmr': 0.0000014393,     'M': 16.043},
        'SO2': {'vmr': 0.0000076267,     'M': 64.066},
        'H2S': {'vmr': 0.00000000027974, 'M': 34.081},
    }

    # Option B: pass mu directly (comment out SPECIES above and uncomment):
    # MU_DIRECT = 2.3  # g/mol

    # ── Compute ────────────────────────────────────────────────────────────────
    res = compute_scale_height(
        M_planet, R_planet, T_eq,
        species=SPECIES,          # or: mu=MU_DIRECT
        M_unit='Mjup',
        R_unit='Rjup',
    )

    print('=' * 60)
    print('MEAN MOLECULAR WEIGHT')
    print('=' * 60)
    mu_val = mean_molecular_weight(SPECIES)
    for name, d in SPECIES.items():
        print(f"  {name:5s}: VMR={d['vmr']:.10f}  M={d['M']:6.3f} g/mol"
              f"  → {d['vmr']*d['M']:.9f}")
    print(f"\n  μ = {mu_val:.6f} g/mol  (method: {res['mu_method']})")

    print('\n' + '=' * 60)
    print('SURFACE GRAVITY')
    print('=' * 60)
    print(f"  g = {res['g']:.4f} m/s²  =  {res['g_cgs']:.2f} cm/s²")

    print('\n' + '=' * 60)
    print('SCALE HEIGHT')
    print('=' * 60)
    print(f"  T_eq = {res['T_eq']} K")
    print(f"  H    = {res['H_m']:.3e} m  =  {res['H_km']:.2f} km")
