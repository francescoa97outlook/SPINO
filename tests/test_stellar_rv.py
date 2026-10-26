"""
When the archive gives no systemic velocity (st_radv), SPINO looks it up in
Gaia DR3 and SIMBAD instead of dropping the telluric page.  The network is
replaced by plain functions here; the parsers are fed the real response
formats of the two services.
"""

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table

import phase_stellar_rv as srv


GAIA_CSV = (
    "source_id,radial_velocity,radial_velocity_error\n"
    "2307504062045842688,-10.715715,0.21564706\n"
)
GAIA_CSV_NO_RV = "source_id,radial_velocity,radial_velocity_error\n4899428146994060800,,\n"


class TestParsers:

    def test_gaia_dr3_csv(self):
        assert srv.parse_gaia_rv_csv(GAIA_CSV) == pytest.approx((-10.715715, 0.21564706))

    def test_gaia_dr3_csv_without_a_velocity(self):
        assert srv.parse_gaia_rv_csv(GAIA_CSV_NO_RV) is None

    def test_gaia_dr3_id_among_simbad_identifiers(self):
        ids = ["LTT 9779", "Gaia DR2 2307504062045842688",
               "Gaia DR3 2307504062045842688", "TIC 183985250"]
        assert srv.gaia_dr3_id(ids) == 2307504062045842688

    def test_no_gaia_dr3_identifier(self):
        assert srv.gaia_dr3_id(["HD 1", "Gaia DR2 123"]) is None

    def test_simbad_velocity(self):
        tab = Table({"rvz_radvel": [5.65], "rvz_err": [1.34],
                     "rvz_bibcode": ["2018yCat.1345....0G"]})
        assert srv.parse_simbad_rv(tab) == (pytest.approx(5.65),
                                            pytest.approx(1.34),
                                            "2018yCat.1345....0G")

    def test_simbad_without_a_velocity(self):
        tab = Table({"rvz_radvel": MaskedColumn([0.0], mask=[True]),
                     "rvz_err": MaskedColumn([0.0], mask=[True]),
                     "rvz_bibcode": [""]})
        assert srv.parse_simbad_rv(tab) is None


def lookups(gaia=None, simbad=None):
    return dict(gaia=lambda host: gaia, simbad=lambda host: simbad)


class TestResolution:

    def test_user_value_wins(self):
        row = {"hostname": "X", "v_sys": 1.0, "st_radv": 2.0}
        got = srv.resolve_systemic_velocity(row, **lookups(gaia=(3.0, 0.1)))
        assert got == (1.0, None, "user")

    def test_archive_value_comes_next(self):
        row = {"hostname": "X", "st_radv": 2.0}
        got = srv.resolve_systemic_velocity(row, **lookups(gaia=(3.0, 0.1)))
        assert got == (2.0, None, "NEA")

    def test_the_more_precise_lookup_is_adopted(self):
        row = {"hostname": "X", "st_radv": np.nan}
        got = srv.resolve_systemic_velocity(
            row, **lookups(gaia=(4.98, 0.84), simbad=(5.65, 1.34, "DR2")))
        assert got == (pytest.approx(4.98), pytest.approx(0.84), "Gaia DR3")

        got = srv.resolve_systemic_velocity(
            row, **lookups(gaia=(14.06, 0.20), simbad=(13.667, 0.077, "B21")))
        assert got == (pytest.approx(13.667), pytest.approx(0.077), "SIMBAD (B21)")

    def test_a_velocity_without_uncertainty_ranks_last(self):
        row = {"hostname": "X", "st_radv": np.nan}
        got = srv.resolve_systemic_velocity(
            row, **lookups(gaia=(4.98, 0.84), simbad=(5.0, np.nan, "ref")))
        assert got[2] == "Gaia DR3"

    def test_nothing_found(self):
        row = {"hostname": "X", "st_radv": np.nan}
        assert srv.resolve_systemic_velocity(row, **lookups()) is None

    def test_failing_lookups_do_not_stop_the_run(self):
        def broken(host):
            raise OSError("offline")
        row = {"hostname": "X", "st_radv": np.nan}
        assert srv.resolve_systemic_velocity(row, gaia=broken, simbad=broken) is None


class TestHostNames:
    """SIMBAD resolves 'TOI-2587' but not the archive's 'TOI-2587 A'.  Only a
    trailing A is dropped: the system name resolves to the primary, so doing
    the same for a B component would return the other star."""

    def test_primary_component_falls_back_to_the_system_name(self):
        assert srv.host_name_candidates("TOI-2587 A") == ["TOI-2587 A", "TOI-2587"]

    def test_other_components_are_kept_as_they_are(self):
        assert srv.host_name_candidates("WASP-94 B") == ["WASP-94 B"]

    def test_plain_names_are_unchanged(self):
        assert srv.host_name_candidates("HATS-5") == ["HATS-5"]

    def test_lookup_tries_the_system_name_after_the_component(self):
        seen = []

        def gaia(host):
            seen.append(host)
            return (-24.71, 0.35) if host == "TOI-2587" else None

        row = {"hostname": "TOI-2587 A", "st_radv": np.nan}
        got = srv.resolve_systemic_velocity(row, gaia=gaia, simbad=lambda h: None)

        assert seen == ["TOI-2587 A", "TOI-2587"]
        assert got == (pytest.approx(-24.71), pytest.approx(0.35), "Gaia DR3")
