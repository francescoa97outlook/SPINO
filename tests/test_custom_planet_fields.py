"""
The custom-planet field list, its example and its help text must stay in sync.

Adding a field in one place and forgetting the other two is silent: the field
still works (custom-planet keys map onto catalogue columns by identity) but the
user never learns it exists.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spino import config_io
from spino.panels import custom_planets_panel as cpp


HELP_CUSTOM = config_io.HELP["Custom Planets"]


def help_keys():
    """Field names covered by the help, expanding the 'a / b' entries."""
    keys = set()
    for entry in HELP_CUSTOM:
        keys.update(part.strip() for part in entry.split("/"))
    return keys


class TestOrbitFieldsAreOffered:

    def test_eccentricity_is_a_custom_planet_field(self):
        assert "pl_orbeccen" in config_io.CUSTOM_PLANET_FIELDS

    def test_argument_of_periastron_is_a_custom_planet_field(self):
        assert "pl_orblper" in config_io.CUSTOM_PLANET_FIELDS

    def test_the_two_are_adjacent_and_in_orbit_order(self):
        fields = config_io.CUSTOM_PLANET_FIELDS
        assert fields.index("pl_orblper") == fields.index("pl_orbeccen") + 1


class TestFieldsExampleAndHelpAgree:

    @pytest.mark.parametrize("field", config_io.CUSTOM_PLANET_FIELDS)
    def test_every_field_is_documented(self, field):
        assert field in help_keys(), f"{field} has no help entry"

    @pytest.mark.parametrize("field", config_io.CUSTOM_PLANET_FIELDS)
    def test_every_field_appears_in_the_inserted_example(self, field):
        assert field in cpp._EXAMPLE, f"{field} missing from the example"

    def test_example_carries_the_documented_defaults(self):
        assert cpp._EXAMPLE["pl_orbeccen"] == 0.0
        assert cpp._EXAMPLE["pl_orblper"] == 90.0


class TestHelpExplainsNull:
    """Leaving a field null is meaningful, not merely tolerated, and the two
    orbit fields mean different things when null."""

    def test_eccentricity_help_mentions_null(self):
        assert "null" in HELP_CUSTOM["pl_orbeccen"].lower()

    def test_argument_of_periastron_help_mentions_null(self):
        assert "null" in HELP_CUSTOM["pl_orblper"].lower()

    def test_argument_of_periastron_help_explains_the_envelope(self):
        text = HELP_CUSTOM["pl_orblper"].lower()
        assert "envelope" in text or "all " in text

    def test_argument_of_periastron_help_states_its_unit(self):
        assert "[deg]" in HELP_CUSTOM["pl_orblper"]
