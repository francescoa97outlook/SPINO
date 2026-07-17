"""
GraphicsConfig - Loads and exposes all values from graphics.yaml.

Singleton loaded once at import time.  Every graphics-related module
(ScaleManager, WindowConfig, etc.) reads from here instead of using
hardcoded constants.
"""

from pathlib import Path
from typing import Any, Dict

import yaml


def _load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


# Resolve path: this file lives in spino/gui_toolkit/layout/,
# and graphics.yaml sits at spino/gui_toolkit/graphics.yaml.
_YAML_PATH = (
    Path(__file__).resolve().parent.parent / "graphics.yaml"
)

# Fallback defaults (used only if the YAML is missing or a key is absent)
_DEFAULTS: Dict[str, Any] = {
    # Window
    "aspect_ratio": 1.75,
    "min_width": 1400,
    "min_height": 800,
    "max_width": 2450,
    "max_height": 1400,
    "default_width": 1750,
    "default_height": 1000,
    "screen_scale_factor": 0.85,
    "macos_scale_factor": 0.95,
    # Panel
    "panel_margin": 50,
    "panel_vertical_spacing": 10,
    "input_panel_ratio": 0.85,
    # Scaling
    "reference_height": 1000,
    "min_scale": 0.8,
    "max_scale": 1.35,
    # Font families
    "font_family": "Sans",
    "font_family_accent": "Arial",
    # Font sizes
    "font_size_label": 9,
    "font_size_label_large": 12,
    "font_size_label_italic": 9,
    "font_size_label_normal": 10,
    "font_size_button": 12,
    "font_size_entry": 10,
    "font_size_link": 10,
    "font_size_help_icon": 16,
    "font_size_help_title": 18,
    "font_size_help_param": 12,
    "font_size_help_text": 10,
    "font_size_tab": 9,
    "font_size_tree": 10,
    "tree_row_height": 25,
    # Matplotlib plot font sizes
    "plot_font_size_label": 13,
    "plot_font_size_title": 14,
    "plot_font_size_tick": 11,
    "plot_font_size_legend": 11,
}

try:
    _raw = _load_yaml(_YAML_PATH)
except Exception as exc:
    print(f"Warning: could not load graphics.yaml ({exc}), using defaults.")
    _raw = {}

# Merge: YAML values win, missing keys fall back to _DEFAULTS
_cfg: Dict[str, Any] = {**_DEFAULTS, **(_raw or {})}


class GraphicsConfig:
    """Read-only access to every graphics.yaml value."""

    # Window -----------------------------------------------------------
    ASPECT_RATIO: float = float(_cfg["aspect_ratio"])
    MIN_WIDTH: int = int(_cfg["min_width"])
    MIN_HEIGHT: int = int(_cfg["min_height"])
    MAX_WIDTH: int = int(_cfg["max_width"])
    MAX_HEIGHT: int = int(_cfg["max_height"])
    DEFAULT_WIDTH: int = int(_cfg["default_width"])
    DEFAULT_HEIGHT: int = int(_cfg["default_height"])
    SCREEN_SCALE_FACTOR: float = float(_cfg["screen_scale_factor"])
    MACOS_SCALE_FACTOR: float = float(_cfg["macos_scale_factor"])

    # Panel layout -----------------------------------------------------
    PANEL_MARGIN: int = int(_cfg["panel_margin"])
    PANEL_VERTICAL_SPACING: int = int(_cfg["panel_vertical_spacing"])
    INPUT_PANEL_RATIO: float = float(_cfg["input_panel_ratio"])

    # Scaling ----------------------------------------------------------
    REFERENCE_HEIGHT: int = int(_cfg["reference_height"])
    MIN_SCALE: float = float(_cfg["min_scale"])
    MAX_SCALE: float = float(_cfg["max_scale"])

    # Font families ----------------------------------------------------
    FONT_FAMILY: str = str(_cfg["font_family"])
    FONT_FAMILY_ACCENT: str = str(_cfg["font_family_accent"])

    # Font sizes (base, at scale = 1.0) --------------------------------
    FONT_SIZE_LABEL: int = int(_cfg["font_size_label"])
    FONT_SIZE_LABEL_LARGE: int = int(_cfg["font_size_label_large"])
    FONT_SIZE_LABEL_ITALIC: int = int(_cfg["font_size_label_italic"])
    FONT_SIZE_LABEL_NORMAL: int = int(_cfg["font_size_label_normal"])
    FONT_SIZE_BUTTON: int = int(_cfg["font_size_button"])
    FONT_SIZE_ENTRY: int = int(_cfg["font_size_entry"])
    FONT_SIZE_LINK: int = int(_cfg["font_size_link"])
    FONT_SIZE_HELP_ICON: int = int(_cfg["font_size_help_icon"])
    FONT_SIZE_HELP_TITLE: int = int(_cfg["font_size_help_title"])
    FONT_SIZE_HELP_PARAM: int = int(_cfg["font_size_help_param"])
    FONT_SIZE_HELP_TEXT: int = int(_cfg["font_size_help_text"])
    FONT_SIZE_TAB: int = int(_cfg["font_size_tab"])
    FONT_SIZE_TREE: int = int(_cfg["font_size_tree"])
    TREE_ROW_HEIGHT: int = int(_cfg["tree_row_height"])

    # Matplotlib plot font sizes ------------------------------------------
    PLOT_FONT_SIZE_LABEL: int = int(_cfg["plot_font_size_label"])
    PLOT_FONT_SIZE_TITLE: int = int(_cfg["plot_font_size_title"])
    PLOT_FONT_SIZE_TICK: int = int(_cfg["plot_font_size_tick"])
    PLOT_FONT_SIZE_LEGEND: int = int(_cfg["plot_font_size_legend"])
