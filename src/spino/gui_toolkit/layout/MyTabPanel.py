from spino.gui_toolkit.layout.MyPanel import MyPanel
from tkinter.ttk import Notebook
from typing import Any, Dict, List


class MyTabPanel(Notebook):
    """
    A custom tabbed panel widget that extends tkinter's Notebook.
    
    This class creates a tabbed interface with multiple panels, each with its own
    background color and content. It provides a clean way to organize related
    content into separate tabs.
    
    Attributes:
        tab_list (List[MyPanel]): List of panel widgets for each tab
    """

    def __init__(
        self,
        parent: Any,
        row: int,
        column: int,
        tab_list,
        columnspan=1,
        rowspan=1,
        **kwargs
    ) -> None:
        """
        Initialize the MyTabPanel widget.

        Args:
            parent: The parent widget
            row: Row position in the parent's grid
            column: Column position in the parent's grid
            tab_list: List of tuples containing (tab_name, tab_color) for each tab
            rowspan: Row span
            columnspan: Column span
            **kwargs: Additional keyword arguments passed to the Notebook widget
        """
        # Initialize the parent Notebook class
        super().__init__(parent, **kwargs)
        
        # Initialize the list to store tab panels
        self.tab_list = []
        
        # Create a panel for each tab
        for counter, tab in enumerate(tab_list):
            # Create a new panel with the specified color
            self.tab_list.append(MyPanel(self, tab[1], 0, 0))
            # Add the panel to the notebook with the specified name
            self.add(self.tab_list[counter], text=tab[0])
        
        # Grid the notebook into the parent
        self.grid(row=row, column=column, columnspan=columnspan, rowspan=rowspan, sticky="nsew")

    def get_list(self) -> List[MyPanel]:
        """
        Get the list of panel widgets for all tabs.

        Returns:
            List[MyPanel]: List of panel widgets, one for each tab
        """
        return self.tab_list



