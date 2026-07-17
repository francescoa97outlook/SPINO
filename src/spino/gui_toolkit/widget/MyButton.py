from tkinter import Button, Frame
from typing import Any, Dict

from spino.gui_toolkit.layout.ScaleManager import ScaleManager


class MyButton(Frame):
    """
    A custom button widget that wraps tkinter's Button in a Frame for better layout control.
    
    This class creates a button with customizable appearance and behavior, inheriting from Frame
    to provide better grid layout management and consistent styling.
    
    Attributes:
        button (Button): The underlying tkinter Button widget
    """

    def __init__(
        self,
        parent: Any,
        row: int,
        column: int,
        text: str,
        bg: str,
        command,
        color_panel: str = "#AAAAAA",
        fg: str = "black",
        size_text: int = 12,
        columnspan: int = 1,
        sticky: str = "NSEW",
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Initialize the MyButton widget.

        Args:
            parent: The parent widget
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            text: Text to display on the button
            bg: Background color of the button
            command: Function to call when button is clicked
            color_panel: Background color of the containing frame
            fg: Text color of the button
            size_text: Font size of the button text
            columnspan: Number of columns the button should span
            sticky: Grid sticky parameter for button placement
            **kwargs: Additional keyword arguments passed to the Button widget
        """
        # Initialize the parent Frame class
        super().__init__(parent, bg=color_panel)
        
        # Create a Button within this Frame
        self.button = Button(self, command=command, **kwargs)
        
        # Customize the button appearance
        sm = ScaleManager.get()
        button_font = sm.font_button if sm else ("Arial", size_text, "bold")
        self.button.config(
            text=text,
            bg=bg,
            fg=fg,
            font=button_font
        )
        
        # Place the button in a grid layout with one row and one column
        self.button.grid(row=0, column=0, padx=1, pady=1, sticky="NSEW")
        
        # Grid the frame into the parent
        self.grid(row=row, column=column, columnspan=columnspan, sticky=sticky)

    def set_status(self, status) -> None:
        """
        Enable or disable the button.

        Args:
            status: The state to set the button to ('normal', 'disabled', etc.)
        """
        self.button.config(state=status)

