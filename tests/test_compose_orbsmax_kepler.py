"""
compose_best_rows must not adopt a pl_orbsmax just because it is the most
recently published value for that field: reproduces the HD 219666 b
regression, where Oddo et al. 2023's a=0.104 AU (the newest pl_orbsmax on
record) is physically incompatible with P=6.0435 d and M*=0.92 Msun via
Kepler's 3rd law, while the older Esposito et al. 2019 value of 0.06356 AU
is consistent to within 1%.  Composing pl_orbsmax field-by-field, blind to
which reference measured it, silently produced a self-inconsistent orbit.
"""

import numpy as np
import pandas as pd
import pytest

import phase_scheduler as sched


def _rows(pubdates, refnames, orbsmax, orbper=None):
    P = orbper if orbper is not None else [6.043450, 6.036070]
    return pd.DataFrame({
        "pl_name":        ["HD 219666 b", "HD 219666 b"],
        "pl_pubdate":     pubdates,
        "pl_refname":     refnames,
        "pl_orbper":      P,
        "pl_tranmid":     [2459084.0, 2458329.0],
        "ra":             [349.5592665, 349.5592665],
        "dec":            [-56.9039857, -56.9039857],
        "pl_orbsmax":     orbsmax,
        "pl_orbsmaxerr1": [0.00200, 0.00100],
        "pl_orbsmaxerr2": [-0.00200, -0.00100],
        "st_mass":        [0.92, 0.92],
    })


def _hd219666b_rows():
    return _rows(
        pubdates=["2023-03", "2019-03"],
        refnames=["Oddo et al. 2023", "Esposito et al. 2019"],
        orbsmax=[0.10400, 0.06356],
    )


class TestKeplerReconciliation:

    def test_rejects_incompatible_recent_donor(self):
        out = sched.compose_best_rows(_hd219666b_rows())

        row = out.iloc[0]
        assert row["pl_orbsmax"] == pytest.approx(0.06356, rel=1e-6)
        assert row["_field_sources"]["pl_orbsmax"] == "Esposito et al. 2019"
        assert row["pl_orbsmaxerr1"] == pytest.approx(0.00100)

    def test_logs_the_rejected_reference(self, capsys):
        sched.compose_best_rows(_hd219666b_rows())

        out = capsys.readouterr().out
        assert "HD 219666 b" in out
        assert "0.104" in out
        assert "Oddo" in out

    def test_leaves_already_consistent_value_untouched(self, capsys):
        # Here the *most recent* donor is already Kepler-consistent, so
        # nothing needs correcting and no warning should fire.
        df = _rows(
            pubdates=["2023-03", "2019-03"],
            refnames=["Esposito-like 2023", "Oddo-like 2019"],
            orbsmax=[0.06356, 0.10400],
        )

        out = sched.compose_best_rows(df)

        row = out.iloc[0]
        assert row["pl_orbsmax"] == pytest.approx(0.06356, rel=1e-6)
        assert row["_field_sources"]["pl_orbsmax"] == "Esposito-like 2023"
        assert "incompatible" not in capsys.readouterr().out.lower()

    def test_falls_back_to_kepler_estimate_when_no_donor_agrees(self, capsys):
        df = _hd219666b_rows()
        df["pl_orbsmax"] = [0.10400, 0.20000]   # neither is consistent

        out = sched.compose_best_rows(df)

        row = out.iloc[0]
        a_kepler = sched._a_from_kepler(row["pl_orbper"], row["st_mass"])
        assert row["pl_orbsmax"] == pytest.approx(a_kepler, rel=1e-9)
        assert row["_field_sources"]["pl_orbsmax"] == "Kepler's 3rd law"
        assert np.isnan(row["pl_orbsmaxerr1"])

    def test_custom_planets_are_not_touched(self):
        # Sanity check on the injection order this fix relies on:
        # CUSTOM_PLANETS is merged into df_best *after* compose_best_rows
        # runs (phase_scheduler.py, main()), so a hand-entered pl_orbsmax
        # never goes through this reconciliation at all.  Nothing to
        # assert here beyond compose_best_rows itself staying a pure
        # function of its input DataFrame.
        df = _hd219666b_rows()
        out1 = sched.compose_best_rows(df.copy())
        out2 = sched.compose_best_rows(df.copy())
        assert out1["pl_orbsmax"].iloc[0] == out2["pl_orbsmax"].iloc[0]
