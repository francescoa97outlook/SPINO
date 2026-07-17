from tkinter.ttk import Treeview
from tkinter import NO, CENTER
from typing import Any, List, Optional


class MyTable(Treeview):
    """
    A custom table widget that extends tkinter's Treeview for displaying tabular data.
    
    This class creates a table widget with customizable columns, widths, and types.
    It provides a clean interface for displaying and interacting with tabular data.
    
    Attributes:
        column_types (List[str]): List of data types for each column
    """

    def __init__(
        self,
        parent: Any,
        table_columns: List[str],
        width_columns: List[int],
        list_type: Optional[List[type]] = None,
        height: Optional[int] = None
    ) -> None:
        """
        Initialize the MyTable widget.

        Args:
            parent: The parent widget
            table_columns: List of column names
            width_columns: List of column widths in pixels
            list_type: List of data types for each column (defaults to all strings)
            height: Height of the table in rows (None for auto-height)
        """
        super().__init__(parent)
        
        # Set default column types if not provided
        if list_type is None:
            list_type = [str for _ in width_columns]
            
        # Set table height if specified
        if height is not None:
            self.config(height=height)
            
        # Configure the table
        self["columns"] = table_columns
        
        # Configure the first column (tree column)
        self.column("#0", width=0, stretch=NO)
        self.heading("#0", text="", anchor=CENTER)
        
        # Store column types for later validation or formatting use
        self.column_types = list_type
        
        # Configure each column
        for i in range(len(table_columns)):
            self.column(
                table_columns[i],
                anchor=CENTER,
                width=width_columns[i],
            )
            self.heading(
                table_columns[i],
                text=table_columns[i],
                anchor=CENTER
            )
            
            # Special handling for columns starting with "#"
            if table_columns[i][0] == "#":
                self.column(
                    table_columns[i],
                    width=width_columns[i],
                    stretch=NO
                )
                self.heading(table_columns[i], text="", anchor=CENTER)
                
        # Pack the table
        self.pack(fill='both', expand=True, padx=1, pady=1)

    def get_arr_values(self):
        """
        Get the values of the currently selected row.

        Returns:
            Optional[List[Any]]: List of values in the selected row, or None if no row is selected
        """
        curItem = self.focus()
        if not curItem:
            return None
        item = self.item(curItem)
        return item.get("values")

