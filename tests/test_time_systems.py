"""
Epochs reach the archive labelled in several time systems.  Every one of them
is brought to BJD_TDB before it is propagated, except a bare "JD", which the
archive uses for epochs that are already BJD_TDB.
"""

import pytest

import phase_scheduler as sched

T0 = 2458000.0                       # 2017 September, TDB - UTC = 69.184 s
RA, DEC = 150.0, -30.0
TDB_MINUS_UTC_S = 69.184


def shift_s(system_ref):
    return (sched.to_bjd_tdb(T0, system_ref, RA, DEC) - T0) * 86400.0


@pytest.mark.parametrize("ref", ["BJD", "BJD-TDB", "BJD_TDB", "BJD/TDB",
                                 "BJD-TT", "BJD-TBD", None, float("nan")])
def test_barycentric_tdb_labels_are_left_unchanged(ref):
    assert shift_s(ref) == 0.0


def test_a_bare_jd_label_is_read_as_bjd_tdb():
    assert shift_s("JD") == 0.0


@pytest.mark.parametrize("ref", ["BJD-UTC", "UTC-BJD"])
def test_barycentric_utc_gains_tdb_minus_utc(ref):
    assert shift_s(ref) == pytest.approx(TDB_MINUS_UTC_S, abs=0.01)


def test_explicit_jd_utc_is_still_converted_from_the_geocentre():
    # TDB - UTC plus a barycentric light travel time of up to 8.3 min.
    assert abs(shift_s("JD-UTC") - TDB_MINUS_UTC_S) > 1.0
    assert abs(shift_s("JD-UTC")) < 8.4 * 60 + TDB_MINUS_UTC_S


def test_hjd_on_the_tdb_scale_differs_from_hjd_utc_by_tdb_minus_utc():
    assert shift_s("HJD-UTC") - shift_s("HJD-TDB") == pytest.approx(
        TDB_MINUS_UTC_S, abs=0.01)


def test_hjd_to_bjd_moves_by_less_than_the_sun_barycentre_light_time():
    # |BJD - HJD| <= about 8 s; with TDB - UTC on top.
    assert abs(shift_s("HJD-TDB")) < 10.0


def test_bjd_tcb_is_brought_to_tdb():
    # TCB runs ahead of TDB by L_B (t - 1977); about 19 s in 2017.
    assert -25.0 < shift_s("BJD-TCB") < -15.0
