from tkinter import Frame, OptionMenu, StringVar
from typing import Any, Callable, Dict, List, Optional

from spino.gui_toolkit.layout.ScaleManager import ScaleManager
from spino.gui_toolkit.widget.MyLabel import MyLabel


class MyDropdown(Frame):
    """
    A custom dropdown widget that wraps tkinter's OptionMenu in a Frame.
    
    This class creates a dropdown menu with customizable appearance and behavior, inheriting from Frame
    to provide better grid layout management and consistent styling. It can optionally include a label.
    
    Attributes:
        chosen_var (StringVar): The variable that stores the selected option
        dropdown (OptionMenu): The underlying tkinter OptionMenu widget
    """

    def __init__(
        self,
        parent: Any,
        row: int,
        column: int,
        options: Optional[List[str]],
        label_text: Optional[str] = None,
        color: str = "#AAAAAA",
        initial_value: int = 0,
        columnspan: int = 2,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Initialize the MyDropdown widget.

        Args:
            parent: The parent widget
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            options: List of options to display in the dropdown
            label_text: Optional text to display as a label before the dropdown
            color: Background color of the containing frame
            initial_value: Index of the initially selected option
            columnspan: Number of columns the widget should span
            **kwargs: Additional keyword arguments passed to the Frame widget
        """
        # Initialize the parent Frame class
        super().__init__(parent, bg=color, **kwargs)
        
        col_label = 0
        if label_text is not None:
            # Create the Label
            _ = MyLabel(self, 0, 0, color=color, label_text=label_text)
            col_label = 1
            
        # Initialize the StringVar for the OptionMenu
        if options is None:
            options = ["None"]
        self.chosen_var = StringVar(value=options[initial_value])
        
        # Create the OptionMenu with scaled font
        self.dropdown = OptionMenu(self, self.chosen_var, *options)
        sm = ScaleManager.get()
        if sm:
            self.dropdown.config(font=sm.font_entry)
            self.dropdown["menu"].config(font=sm.font_entry)
        self.dropdown.grid(
            column=0 + col_label,
            row=0,
            padx=1,
            pady=1,
            columnspan=columnspan - col_label,
            sticky="ew"
        )
        self.grid_columnconfigure(0 + col_label, weight=1)

        # Grid the frame into the parent
        self.grid(row=row, column=column, columnspan=columnspan, sticky="ew")

    def get_value(self) -> str:
        """
        Get the currently selected value from the dropdown.

        Returns:
            str: The currently selected option
        """
        return self.chosen_var.get()

    def set_value(self, value: str) -> None:
        """
        Set the selected value of the dropdown.

        Args:
            value: The option to select
        """
        self.chosen_var.set(value)

    def set_callback(self, callback_function) -> None:
        """
        Set a callback function that triggers when the dropdown value changes.

        Args:
            callback_function: Function to call when selection changes
        """
        self.chosen_var.trace("w", lambda *args: callback_function())

    def clean_widget(self) -> None:
        """
        Remove the widget from the display by clearing both grid and place geometry managers.
        """
        self.dropdown.grid_remove()
        self.dropdown.place_forget()
        self.grid_remove()
        self.place_forget()

    def set_status(self, status) -> None:
        """
        Enable or disable the dropdown.

        Args:
            status: The state to set the dropdown to ('normal', 'disabled', etc.)
        """
        self.dropdown.config(state=status)
