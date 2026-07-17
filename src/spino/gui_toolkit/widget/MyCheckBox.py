import tkinter as tk
from tkinter import Checkbutton, Frame
from typing import Any, Dict

from spino.gui_toolkit.layout.ScaleManager import ScaleManager


class MyCheckBox(Frame):
    """
    A custom checkbox widget that wraps tkinter's Checkbutton in a Frame.
    
    This class creates a checkbox with customizable appearance and behavior, inheriting from Frame
    to provide better grid layout management and consistent styling.
    
    Attributes:
        var (IntVar): The variable that stores the checkbox state (0 or 1)
        checkbox (Checkbutton): The underlying tkinter Checkbutton widget
    """

    def __init__(
        self,
        parent: Any,
        row: int,
        column: int,
        text: str = "",
        initial_value: int = 0,
        **kwargs
    ) -> None:
        """
        Initialize the MyCheckBox widget.

        Args:
            parent: The parent widget
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            text: Text to display next to the checkbox
            initial_value: Initial state of the checkbox (0 for unchecked, 1 for checked)
            **kwargs: Additional keyword arguments passed to the Checkbutton widget
        """
        # Initialize the parent Frame class
        super().__init__(parent)
        # Initialize the IntVar for the Checkbutton
        self.var = tk.IntVar(value=initial_value)
        # Create the Checkbutton with scaled font
        self.checkbox = Checkbutton(self, text=text, variable=self.var, **kwargs)
        sm = ScaleManager.get()
        if sm:
            self.checkbox.config(font=sm.font_label)
        # Place the Checkbutton in the frame using grid layout
        self.checkbox.grid(row=0, column=0, padx=1, pady=1)
        # Grid the frame into the parent
        self.grid(row=row, column=column)

    def get_value(self) -> int:
        """
        Get the current value of the checkbox.

        Returns:
            int: 0 for unchecked, 1 for checked
        """
        return self.var.get()

    def set_value(self, value: int) -> None:
        """
        Set the value of the checkbox.

        Args:
            value: 0 for unchecked, 1 for checked
        """
        self.var.set(value)

    def set_status(self, status) -> None:
        """
        Enable or disable the checkbox.

        Args:
            status: The state to set the checkbox to ('normal', 'disabled', etc.)
        """
        self.checkbox.config(state=status)
