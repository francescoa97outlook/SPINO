from tkinter import Frame
from typing import Any


class MyPanel(Frame):
    """
    A custom panel widget that extends tkinter's Frame with additional layout capabilities.
    
    This class creates a panel with customizable appearance and behavior, inheriting from Frame
    to provide better grid layout management and consistent styling. It includes automatic
    column configuration and visibility control.
    """

    def __init__(
        self,
        parent: Any,
        color: str,
        row: int,
        column: int,
        columnspan: int = 1,
        rowspan: int = 1,
        visible: bool = True,
        **kwargs
    ) -> None:
        """
        Initialize the MyPanel widget.

        Args:
            parent: The parent widget
            color: Background color of the panel
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            columnspan: Number of columns the panel should span
            rowspan: Number of rows the panel should span
            visible: Whether the panel should be visible initially
            **kwargs: Additional keyword arguments passed to the Frame widget
        """
        # Initialize the parent Frame class with custom styling
        super().__init__(
            parent,
            bg=color,
            highlightbackground="black",
            highlightthickness=1,
            **kwargs
        )
        
        # Configure the panel's grid layout if visible
        if visible:
            self.grid(
                row=row,
                column=column,
                sticky="NSEW",
                rowspan=rowspan,
                columnspan=columnspan
            )
            # Configure column weights for responsive layout
            self.grid_columnconfigure((0, 100), weight=1)

