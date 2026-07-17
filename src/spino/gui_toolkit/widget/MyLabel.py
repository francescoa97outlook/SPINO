from tkinter import Frame, Label
from typing import Any, Dict, Optional, Tuple

from spino.gui_toolkit.layout.ScaleManager import ScaleManager


class MyLabel(Frame):
    """
    A custom label widget that wraps tkinter's Label in a Frame.
    
    This class creates a text label with customizable appearance and behavior, inheriting from Frame
    to provide better grid layout management and consistent styling.
    
    Attributes:
        label (Label): The underlying tkinter Label widget
    """

    def __init__(
        self,
        parent: Any,
        row: int,
        column: int,
        color: str = "#AAAAAA",
        label_text: str = "Label",
        font: Optional[Tuple[str, int, str]] = None,
        columnspan: int = 1,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Initialize the MyLabel widget.

        Args:
            parent: The parent widget
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            color: Background color of the label
            label_text: Text to display in the label
            font: Font specification (family, size, style)
            columnspan: Number of columns the label should span
            **kwargs: Additional keyword arguments passed to the Label widget
        """
        # Initialize the parent Frame class
        super().__init__(parent, bg=color)

        # Resolve default font via ScaleManager
        if font is None:
            sm = ScaleManager.get()
            font = sm.font_label if sm else ("Sans", 9, "bold")

        # Create the Label
        self.label = Label(
            self,
            text=label_text,
            font=font,
            bg=color,
            **kwargs
        )
        
        # Place the Label in the frame using grid layout
        self.label.grid(
            column=0,
            row=0,
            columnspan=columnspan,
            padx=1,
            pady=1,
            sticky="w"
        )

        # Grid the frame into the parent
        self.grid(row=row, column=column, columnspan=columnspan, sticky="w")

    def set_text(self, text: str) -> None:
        """
        Set the text of the label.

        Args:
            text: The new text to display
        """
        self.label.config(text=text)

    def get_text(self) -> str:
        """
        Get the current text of the label.

        Returns:
            str: The current text displayed in the label
        """
        return self.label.cget("text")
