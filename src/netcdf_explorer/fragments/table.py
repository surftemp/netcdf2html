#    Copyright (C) 2023  University of Reading (NCEO)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

from ..htmlfive.html5_builder import Html5Builder, Fragment, ElementFragment

class TableFragment(ElementFragment):

    def __init__(self, attrs={},style={}):
        super().__init__("table",attrs,style)
        self.thead = self.add_element("thead")
        self.tbody = self.add_element("tbody")

    def set_column_ids(self, column_ids, columns_hidden=None):
        for idx in range(len(column_ids)):
            style = {}
            if columns_hidden and columns_hidden[idx]:
                style["visibility"] = "collapse"
            self.add_element("col",attrs={"id":column_ids[idx]}, style=style)

    def add_row(self, cells, tr_attrs={}, style={}):
        tr = self.tbody.add_element("tr", tr_attrs, style)
        if isinstance(cells,str):
            tr.add_element("td",attrs={"colspan":"100%"}).add_text(cells)
        else:
            for cell in cells:
                td = tr.add_element("td")
                if isinstance(cell,str):
                    td.add_text(cell)
                else:
                    td.add_fragment(cell)

    def add_header_row(self, cells):
        tr = self.thead.add_element("tr")
        for cell in cells:
            td = tr.add_element("th")
            if isinstance(cell,str):
                td.add_text(cell)
            else:
                td.add_fragment(cell)




