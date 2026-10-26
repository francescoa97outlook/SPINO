"""
The choice of using eccentricity upper limits as values is a preset key like
every other: it has a default, and exactly one GUI panel saves and restores it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spino import config_io
from spino.panels import (catalog_panel, constraints_panel,
                          custom_planets_panel, filters_panel,
                          observatory_panel, output_panel, telluric_panel)

PANELS = [catalog_panel.CatalogPanel, filters_panel.FiltersPanel,
          observatory_panel.ObservatoryPanel,
          constraints_panel.ConstraintsPanel,
          custom_planets_panel.CustomPlanetsPanel,
          telluric_panel.TelluricPanel, output_panel.OutputPanel]


def test_upper_limits_are_off_by_default():
    assert config_io.load_defaults()["USE_ECC_UPPER_LIMITS"] is False


def test_every_preset_key_is_owned_by_exactly_one_panel():
    owners = {}
    for panel in PANELS:
        for key in panel.KEYS:
            owners.setdefault(key, []).append(panel.__name__)

    for key in config_io.CONFIG_KEYS:
        assert len(owners.get(key, [])) == 1, f"{key}: {owners.get(key)}"


def test_the_option_is_documented():
    assert "USE_ECC_UPPER_LIMITS" in config_io.HELP["Catalog"]
