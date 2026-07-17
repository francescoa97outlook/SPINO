import numpy as np
import pandas as pd
from scipy.constants import h, c, k


class TSM_ESM_Calculator:
    """
    Transmission / Emission Spectroscopy Metrics (Kempton et al. 2018)
    PASP, 130, 114401 - doi:10.1088/1538-3873/aadf6f

    TSM = ScaleFactor × (Rp³ Teq) / (Mp Rs²) × 10^(−mJ/5)       [Eq. 1]
    ESM = 4.29×10⁶ × B₇.₅(Tday)/B₇.₅(T★) × (Rp/R★)² × 10^(−mK/5) [Eq. 4]
    Tday = 1.10 × Teq
    """

    # Scale factors (Table 1)
    SCALE = {
        'terrestrial':       0.190,   # Rp < 1.5
        'small_sub_neptune': 1.26,    # 1.5 ≤ Rp < 2.75
        'large_sub_neptune': 1.28,    # 2.75 ≤ Rp < 4.0
        'sub_jovian':        1.15,    # 4.0 ≤ Rp < 10.0
    }

    # Recommended TSM thresholds (Section 5 / Figure 5)
    TSM_THR = {
        'terrestrial': 10,
        'small_sub_neptune': 90,
        'large_sub_neptune': 90,
        'sub_jovian': 90,
    }
    ESM_THR = 7.5   # GJ 1132b benchmark

    R_EARTH_CM = 6.371e8
    R_SUN_CM   = 6.957e10
    RHO_EARTH  = 5.515        # g cm⁻³
    RJUP2REARTH = 11.2
    MJUP2MEARTH = 317.8

    # -------------------------------------------------------------- #
    #  Chen & Kipping (2017) mass–radius relation  (Kempton Eq. 2)   #
    # -------------------------------------------------------------- #
    @staticmethod
    def _mass_from_radius(rp):
        if rp < 1.23:
            return 0.9718 * rp ** 3.58
        else:
            return 1.436  * rp ** 1.70

    # -------------------------------------------------------------- #
    #  Teq  (Kempton Eq. 3): zero albedo, full redistribution      #
    # -------------------------------------------------------------- #
    @staticmethod
    def _teq(t_star, r_star_rsun, a_au):
        r_star_au = r_star_rsun * 0.00465047
        return t_star * np.sqrt(r_star_au / a_au) * 0.25 ** 0.25

    # -------------------------------------------------------------- #
    #  Planck function at λ = 7.5 µm                                  #
    # -------------------------------------------------------------- #
    @staticmethod
    def _B(T, lam_um=7.5):
        lam = lam_um * 1e-6
        return (2*h*c**2 / lam**5) / (np.exp(h*c/(lam*k*T)) - 1)

    # -------------------------------------------------------------- #
    #  Category                                                       #
    # -------------------------------------------------------------- #
    @staticmethod
    def _category(rp):
        if   rp <  1.5:  return 'terrestrial'
        elif rp <  2.75: return 'small_sub_neptune'
        elif rp <  4.0:  return 'large_sub_neptune'
        elif rp <= 10.0: return 'sub_jovian'
        else:            return 'giant'

    # ============================================================== #
    #  MAIN METHOD                                                    #
    # ============================================================== #
    def compute(self, p):
        """
        Parameters
        ----------
        p : dict, single self-contained planet dictionary.

        Required keys
        -------------
        name          : str    (planet identifier)
        Rp_Rearth  OR  Rp_Rjup   (planet radius)
        Rs_Rsun       : float  (stellar radius, [R☉])
        Teff_star     : float  (stellar Teff, [K])
        mag_J         : float  (host star J mag)
        mag_K         : float  (host star K mag)

        Plus ONE of:
            Teq         : float  (equilibrium temperature [K])
            a_AU        : float  (semi-major axis [AU]; Teq computed)

        Optional
        --------
        Mp_Mearth  OR  Mp_Mjup  (planet mass)
            (if absent → Chen & Kipping 2017 estimate)
        P_days        : float  (orbital period [d])
        a_AU          : float  (semi-major axis [AU])

        Returns
        -------
        dict with TSM, ESM and all intermediates.
        """

        # --- radius ---
        if 'Rp_Rearth' in p:
            rp = p['Rp_Rearth']
        elif 'Rp_Rjup' in p:
            rp = p['Rp_Rjup'] * self.RJUP2REARTH
        else:
            raise KeyError("Provide 'Rp_Rearth' or 'Rp_Rjup'.")

        # --- mass ---
        mass_est = False
        if 'Mp_Mearth' in p:
            mp = p['Mp_Mearth']
        elif 'Mp_Mjup' in p:
            mp = p['Mp_Mjup'] * self.MJUP2MEARTH
        else:
            mp = self._mass_from_radius(rp)
            mass_est = True

        # --- stellar ---
        rs   = p['Rs_Rsun']
        teff = p['Teff_star']
        mj   = p['mag_J']
        mk   = p['mag_K']

        # --- Teq ---
        if 'Teq' in p:
            teq = p['Teq']
        elif 'a_AU' in p:
            teq = self._teq(teff, rs, p['a_AU'])
        else:
            raise KeyError("Provide 'Teq' or 'a_AU'.")

        tday = 1.10 * teq

        # --- category & scale ---
        cat   = self._category(rp)
        sf    = self.SCALE.get(cat, 1.0)
        thr   = self.TSM_THR.get(cat, 90)

        # === TSM (Eq. 1) ===
        tsm = sf * (rp**3 * teq) / (mp * rs**2) * 10**(-mj/5)

        # === ESM (Eq. 4) ===
        bp = self._B(tday)
        bs = self._B(teff)
        rr = (rp * self.R_EARTH_CM) / (rs * self.R_SUN_CM)
        esm = 4.29e6 * (bp/bs) * rr**2 * 10**(-mk/5)

        rho = (mp / rp**3) * self.RHO_EARTH

        return {
            'name': p['name'],
            'Period_days': p.get('P_days', np.nan),  # <--- NUOVO: Periodo
            'Rs_Rsun': round(rs, 3),  # <--- NUOVO: Raggio Stella usato
            'Teff_star': round(teff, 0),  # <--- NUOVO: Teff usata
            'mag_J': mj,  # <--- NUOVO: Mag J usata
            'mag_K': mk,  # <--- NUOVO: Mag K usata
            'Rp_Rearth': round(rp, 4),
            'Mp_Mearth': round(mp, 4),
            'mass_estimated': mass_est,
            'density_gcm3': round(rho, 4),
            'Teq_K': round(teq, 1),
            'category': cat,
            'TSM': round(tsm, 4),
            'TSM_threshold': thr,
            'TSM_above': tsm >= thr,
            'ESM': round(esm, 4),
            'ESM_threshold': self.ESM_THR,
            'ESM_above': esm >= self.ESM_THR,
        }


# ================================================================== #
#  Convenience: analyze a list of planets and print + export          #
# ================================================================== #
def analyze(planets, output_csv="tsm_esm_results.csv"):
    calc = TSM_ESM_Calculator()
    rows = [calc.compute(p) for p in planets]
    df = pd.DataFrame(rows)

    print(f"\n{'=' * 70}")
    for r in rows:
        mflag = " (Chen&Kipping)" if r['mass_estimated'] else ""
        print(f"  {r['name']}")
        print(f"    Rp = {r['Rp_Rearth']:.2f} R⊕   "
              f"Mp = {r['Mp_Mearth']:.2f} M⊕{mflag}   "
              f"ρ = {r['density_gcm3']:.2f} g/cm³")
        print(f"    Teq = {r['Teq_K']:.0f} K   Tday = {r['Tday_K']:.0f} K   "
              f"[{r['category']}]")
        t = '✓' if r['TSM_above'] else '✗'
        e = '✓' if r['ESM_above'] else '✗'
        print(f"    TSM = {r['TSM']:.2f}  {t}  (thr {r['TSM_threshold']})")
        print(f"    ESM = {r['ESM']:.2f}  {e}  (thr {r['ESM_threshold']})")
        print()

    df_s = df.sort_values('TSM', ascending=False)
    print(f"{'─' * 70}")
    print("  RANKING BY TSM")
    for i, (_, r) in enumerate(df_s.iterrows(), 1):
        t = '✓' if r['TSM_above'] else '✗'
        print(f"    {i}. {r['name']:25s} TSM = {r['TSM']:9.2f}  {t}")
    print(f"{'=' * 70}\n")

    df.to_csv(output_csv, index=False)
    print(f"  Saved → {output_csv}\n")
    return df


# ================================================================== #
#  MAIN: inserisci qui i tuoi target                                 #
# ================================================================== #
if __name__ == "__main__":

    planets = [

        # ──────────────────────────────────────────────────────────
        #  Ogni dizionario è UN pianeta, auto-contenuto.
        #  I parametri stellari si ripetono per ogni pianeta.
        #
        #  CHIAVI OBBLIGATORIE:
        #    name:        nome del pianeta
        #    Rp_Rearth:   raggio planetario [R⊕]  (oppure Rp_Rjup)
        #    Rs_Rsun:     raggio stellare   [R☉]
        #    Teff_star:   temperatura stellare [K]
        #    mag_J:       magnitudine J della stella
        #    mag_K:       magnitudine K della stella
        #    Teq:         temperatura di equilibrio [K]
        #                   (oppure a_AU → Teq calcolata da Eq. 3)
        #
        #  CHIAVI OPZIONALI:
        #    Mp_Mearth:   massa planetaria [M⊕]  (oppure Mp_Mjup)
        #                   se assente → relazione M-R Chen&Kipping 2017
        #    a_AU:        semiasse maggiore [AU]
        #    P_days:      periodo orbitale  [giorni]
        # ──────────────────────────────────────────────────────────

        {
            'name':      'Planet b',
            'Rp_Rearth': 3.36,
            'Mp_Mearth': 9.53,
            'Teq':       819,
            'Rs_Rsun':   0.94,
            'Teff_star': 5385,
            'mag_J':     7.6,
            'mag_K':     7.2,
        },

    ]

    df = analyze(planets, output_csv="tsm_esm_results.csv")