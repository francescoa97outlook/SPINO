"""
ScaleManager: Singleton that manages named fonts and handles responsive scaling.

When the main window is resized, all named Font objects are updated automatically,
causing every widget that references them to redraw at the new size.

All configurable values (reference height, scale limits, font families, base
sizes) are read from graphics.yaml via GraphicsConfig.
"""

import tkinter.font as tkfont
from tkinter import ttk

from spino.gui_toolkit.layout.GraphicsConfig import GraphicsConfig as GC


class ScaleManager:
    _instance = None

    @classmethod
    def init(cls, root):
        """
        Initialize the singleton instance. Must be called once after tk.Tk() is created.

        Args:
            root: The root tkinter Tk widget.

        Returns:
            ScaleManager: The singleton instance.
        """
        cls._instance = cls(root)
        return cls._instance

    @classmethod
    def get(cls):
        """
        Get the singleton instance.

        Returns:
            ScaleManager or None: The singleton instance, or None if init() has not been called.
        """
        return cls._instance

    def __init__(self, root):
        """
        Initialize the ScaleManager with the root tkinter widget.

        Args:
            root: The root tkinter Tk widget used for resize event binding.
        """
        self._root = root
        self._scale = 1.0
        self._resize_timer = None

        ff = GC.FONT_FAMILY          # general font family
        fa = GC.FONT_FAMILY_ACCENT   # accent font family

        # Named fonts: base sizes come from graphics.yaml
        self.font_label        = tkfont.Font(family=ff, size=GC.FONT_SIZE_LABEL,        weight="bold")
        self.font_label_large  = tkfont.Font(family=ff, size=GC.FONT_SIZE_LABEL_LARGE,  weight="bold")
        self.font_label_italic = tkfont.Font(family=ff, size=GC.FONT_SIZE_LABEL_ITALIC, slant="italic")
        self.font_label_normal = tkfont.Font(family=ff, size=GC.FONT_SIZE_LABEL_NORMAL)
        self.font_button       = tkfont.Font(family=fa, size=GC.FONT_SIZE_BUTTON,       weight="bold")
        self.font_entry        = tkfont.Font(family=ff, size=GC.FONT_SIZE_ENTRY)
        self.font_link         = tkfont.Font(family=fa, size=GC.FONT_SIZE_LINK,         underline=True)
        self.font_help_icon    = tkfont.Font(family=fa, size=GC.FONT_SIZE_HELP_ICON,    weight="bold")
        self.font_help_title   = tkfont.Font(family=fa, size=GC.FONT_SIZE_HELP_TITLE,   weight="bold")
        self.font_help_param   = tkfont.Font(family=fa, size=GC.FONT_SIZE_HELP_PARAM,   weight="bold")
        self.font_help_text    = tkfont.Font(family=fa, size=GC.FONT_SIZE_HELP_TEXT)

        # Registry: (font_object, base_size) for scaling
        self._fonts = [
            (self.font_label,        GC.FONT_SIZE_LABEL),
            (self.font_label_large,  GC.FONT_SIZE_LABEL_LARGE),
            (self.font_label_italic, GC.FONT_SIZE_LABEL_ITALIC),
            (self.font_label_normal, GC.FONT_SIZE_LABEL_NORMAL),
            (self.font_button,       GC.FONT_SIZE_BUTTON),
            (self.font_entry,        GC.FONT_SIZE_ENTRY),
            (self.font_link,         GC.FONT_SIZE_LINK),
            (self.font_help_icon,    GC.FONT_SIZE_HELP_ICON),
            (self.font_help_title,   GC.FONT_SIZE_HELP_TITLE),
            (self.font_help_param,   GC.FONT_SIZE_HELP_PARAM),
            (self.font_help_text,    GC.FONT_SIZE_HELP_TEXT),
        ]

        # ttk styles for Notebook tabs and Treeview
        self._style = ttk.Style()
        self._update_ttk_styles()

        # Bind resize
        root.bind('<Configure>', self._on_configure)

    @property
    def scale(self):
        """The current scale factor (float)."""
        return self._scale

    def _on_configure(self, event):
        if event.widget != self._root:
            return
        if self._resize_timer is not None:
            self._root.after_cancel(self._resize_timer)
        self._resize_timer = self._root.after(150, self._apply_scale, event.height)

    def _apply_scale(self, new_height):
        self._resize_timer = None
        new_scale = max(GC.MIN_SCALE, min(GC.MAX_SCALE, new_height / GC.REFERENCE_HEIGHT))
        if abs(new_scale - self._scale) < 0.03:
            return
        self._scale = new_scale
        for font_obj, base_size in self._fonts:
            font_obj.configure(size=max(7, int(base_size * self._scale)))
        self._update_ttk_styles()

    def _update_ttk_styles(self):
        ff = GC.FONT_FAMILY
        tab_size = max(7, int(GC.FONT_SIZE_TAB * self._scale))
        tree_size = max(7, int(GC.FONT_SIZE_TREE * self._scale))
        row_height = max(20, int(GC.TREE_ROW_HEIGHT * self._scale))
        self._style.configure("TNotebook.Tab", font=(ff, tab_size, "bold"))
        self._style.configure("Treeview", font=(ff, tree_size), rowheight=row_height)
        self._style.configure("Treeview.Heading", font=(ff, tab_size, "bold"))

    def scaled(self, base_size):
        """
        Get a scaled integer size for one-off uses.

        Args:
            base_size: The base font size to scale.

        Returns:
            int: The scaled size, with a minimum of 7.
        """
        return max(7, int(base_size * self._scale))
