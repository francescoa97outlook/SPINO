import tkinter as tk
from tkinter import Frame, Text
from typing import Any, Optional

from spino.gui_toolkit.layout.ScaleManager import ScaleManager
from spino.gui_toolkit.widget.MyLabel import MyLabel


class MyTextField(Frame):
    """
    A custom text field widget that wraps tkinter's Text in a Frame.
    
    This class creates a multi-line text input field with customizable appearance and behavior,
    inheriting from Frame to provide better grid layout management and consistent styling.
    It can optionally include a label.
    
    Attributes:
        text_widget (Text): The underlying tkinter Text widget
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
        rowspan: int = 1,
        height: int = 1,
        **kwargs
    ) -> None:
        """
        Initialize the MyTextField widget.

        Args:
            parent: The parent widget
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            text: Initial text to display in the text field
            label_text: Optional text to display as a label before the text field
            color: Background color of the containing frame
            columnspan: Number of columns the widget should span
            rowspan: Number of rows the widget should span
            height: Height of the text field in lines
            **kwargs: Additional keyword arguments passed to the Text widget
        """
        # Initialize the parent Frame class
        super().__init__(parent, bg=color)
        
        col_label = 0
        if label_text is not None:
            # Create the Label
            _ = MyLabel(self, 0, 0, color=color, label_text=label_text)
            col_label = 1
            
        # Create the Text widget with scaled font
        sm = ScaleManager.get()
        text_kwargs = dict(**kwargs)
        if sm:
            text_kwargs["font"] = sm.font_entry
        self.text_widget = Text(self, height=height, **text_kwargs)
        self.text_widget.insert(tk.END, text)
        self.text_widget.grid(
            column=1,
            row=0,
            columnspan=columnspan - col_label,
            padx=1,
            pady=1,
            sticky="ew"
        )
        self.grid_columnconfigure(1, weight=1)

        # Grid the frame into the parent
        self.grid(row=row, column=column, columnspan=columnspan, rowspan=rowspan, sticky="ew")

    def insert_text(self, text: str) -> None:
        """
        Replace the current text in the text field with new text.

        Args:
            text: The new text to display
        """
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(tk.END, text)

    def get_text(self) -> str:
        """
        Get the current text from the text field.

        Returns:
            str: The current text in the text field, with leading/trailing whitespace removed
        """
        return self.text_widget.get(1.0, tk.END).strip()

    def set_status(self, status) -> None:
        """
        Enable or disable the text field.

        Args:
            status: The state to set the text field to ('normal', 'disabled', etc.)
        """
        self.text_widget.config(state=status)
