import tkinter as tk
from tkinter import Frame, Entry
from typing import Any, Dict, Optional

from spino.gui_toolkit.layout.ScaleManager import ScaleManager
from spino.gui_toolkit.widget.MyLabel import MyLabel


class MyEntry(Frame):
    """
    A custom entry widget that wraps tkinter's Entry in a Frame.
    
    This class creates a text entry field with customizable appearance and behavior, inheriting from Frame
    to provide better grid layout management and consistent styling. It can optionally include a label.
    
    Attributes:
        entry (Entry): The underlying tkinter Entry widget
    """

    def __init__(
        self,
        parent: Any,
        row: int,
        column: int,
        text: str,
        label_text: Optional[str] = None,
        color: str = "#AAAAAA",
        columnspan: int = 2,
        entry_width: int = 10,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Initialize the MyEntry widget.

        Args:
            parent: The parent widget
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            text: Initial text to display in the entry field
            label_text: Optional text to display as a label before the entry field
            color: Background color of the containing frame
            columnspan: Number of columns the widget should span
            entry_width: Width of the entry field in characters
            **kwargs: Additional keyword arguments passed to the Entry widget
        """
        # Initialize the parent Frame class
        super().__init__(parent, bg=color)
        
        col_label = 0
        if label_text is not None:
            # Create the Label
            _ = MyLabel(self, 0, 0, color=color, label_text=label_text)
            col_label = 1
            
        # Create the Entry widget with scaled font
        sm = ScaleManager.get()
        entry_font = sm.font_entry if sm else None
        entry_kwargs = dict(**kwargs)
        if entry_font:
            entry_kwargs["font"] = entry_font
        self.entry = Entry(self, width=entry_width, **entry_kwargs)
        self.entry.insert(tk.END, str(text))
        self.entry.grid(
            column=1,
            row=0,
            columnspan=columnspan - col_label,
            padx=1,
            pady=1,
            sticky="ew"
        )
        self.grid_columnconfigure(1, weight=1)

        # Grid the frame into the parent
        self.grid(row=row, column=column, columnspan=columnspan, sticky="ew")

    def get_value(self) -> str:
        """
        Get the current value from the entry field.

        Returns:
            str: The current text in the entry field
        """
        return self.entry.get()

    def set_value(self, value: str) -> None:
        """
        Set the value of the entry field.

        Args:
            value: The text to set in the entry field
        """
        self.entry.delete(0, tk.END)
        self.entry.insert(tk.END, str(value))

    def set_status(self, status) -> None:
        """
        Enable or disable the entry field.

        Args:
            status: The state to set the entry field to ('normal', 'disabled', etc.)
        """
        self.entry.config(state=status)
