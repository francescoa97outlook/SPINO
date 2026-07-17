"""
HelpButton: A reusable help button widget that displays information in a popup.

This module provides a help button with a blue electric background and a yellow-gold
question mark that opens a popup with detailed descriptions when clicked.
"""

import tkinter as tk
from tkinter import ttk

from spino.gui_toolkit.layout.ScaleManager import ScaleManager


class HelpButton:
    """
    A help button widget that displays information in a popup window.

    This button has a blue electric background with a yellow-gold question mark.
    When clicked, it opens a popup window displaying help text.
    """

    def __init__(self, parent, row, column, title, help_text, columnspan=1, rowspan=1, **kwargs):
        """
        Initialize the HelpButton.

        Args:
            parent: Parent widget
            row: Grid row position
            column: Grid column position
            title: Title of the popup window
            help_text: Dictionary with parameter names as keys and descriptions as values
            columnspan: Number of columns to span (default: 1)
            rowspan: Number of rows to span (default: 1)
            **kwargs: Additional keyword arguments for grid configuration
        """
        self.parent = parent
        self.title = title
        self.help_text = help_text

        # Create the button with blue electric background and yellow-gold question mark
        self.button = tk.Button(
            parent,
            text="?",
            bg="#0080FF",  # Electric blue background
            fg="#FFD700",  # Yellow-gold text
            font=ScaleManager.get().font_help_icon if ScaleManager.get() else ("Arial", 16, "bold"),
            width=3,
            height=1,
            relief=tk.RAISED,
            borderwidth=3,
            command=self.show_help_popup
        )

        # Grid the button
        self.button.grid(row=row, column=column, columnspan=columnspan, rowspan=rowspan, padx=2, pady=2, **kwargs)

        # Add hover effect
        self.button.bind("<Enter>", self._on_enter)
        self.button.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        """Change button appearance on mouse enter."""
        self.button.config(bg="#0099FF", relief=tk.SUNKEN)

    def _on_leave(self, event):
        """Restore button appearance on mouse leave."""
        self.button.config(bg="#0080FF", relief=tk.RAISED)

    def show_help_popup(self):
        """Show the help popup window with the help text."""
        # Create popup window
        popup = tk.Toplevel(self.parent)
        popup.title(self.title)
        popup.geometry("700x600")
        popup.configure(bg="white")

        # Make popup modal
        popup.transient(self.parent)
        popup.grab_set()

        # Create main frame with scrollbar
        main_frame = ttk.Frame(popup)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create canvas and scrollbar
        canvas = tk.Canvas(main_frame, bg="white")
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Add title label
        title_label = tk.Label(
            scrollable_frame,
            text=self.title,
            font=ScaleManager.get().font_help_title if ScaleManager.get() else ("Arial", 18, "bold"),
            bg="white",
            fg="#0080FF"
        )
        title_label.pack(pady=(0, 20))

        # Add separator
        separator = ttk.Separator(scrollable_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(0, 20))

        # Add help text entries
        for param_name, description in self.help_text.items():
            # Parameter name frame
            param_frame = tk.Frame(scrollable_frame, bg="white")
            param_frame.pack(fill=tk.X, pady=10, padx=10)

            # Parameter name label
            param_label = tk.Label(
                param_frame,
                text=param_name,
                font=ScaleManager.get().font_help_param if ScaleManager.get() else ("Arial", 12, "bold"),
                bg="white",
                fg="#0080FF",
                anchor="w"
            )
            param_label.pack(anchor="w")

            # Description label
            desc_label = tk.Label(
                param_frame,
                text=description,
                font=ScaleManager.get().font_help_text if ScaleManager.get() else ("Arial", 10),
                bg="white",
                fg="black",
                anchor="w",
                justify=tk.LEFT,
                wraplength=650
            )
            desc_label.pack(anchor="w", padx=(20, 0), pady=(5, 0))

            # Add separator between entries
            entry_separator = ttk.Separator(scrollable_frame, orient=tk.HORIZONTAL)
            entry_separator.pack(fill=tk.X, pady=(10, 0))

        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add close button at the bottom
        button_frame = tk.Frame(popup, bg="white")
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        close_button = tk.Button(
            button_frame,
            text="Close",
            font=ScaleManager.get().font_help_param if ScaleManager.get() else ("Arial", 12, "bold"),
            bg="#0080FF",
            fg="white",
            width=15,
            height=2,
            command=popup.destroy
        )
        close_button.pack()

        # Center the popup window
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (popup.winfo_width() // 2)
        y = (popup.winfo_screenheight() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

        # Bind mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        popup.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def grid_remove(self):
        """Remove the button from the grid."""
        self.button.grid_remove()

    def grid(self, **kwargs):
        """Grid the button with new parameters."""
        self.button.grid(**kwargs)