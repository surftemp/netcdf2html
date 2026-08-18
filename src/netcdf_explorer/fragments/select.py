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

class SelectFragment(ElementFragment):

    def __init__(self, attrs={},style={}):
        super().__init__("select",attrs,style)

    def add_option(self, option_value, option_label, is_selected):
        attrs = {"value":option_value}
        if is_selected:
            attrs["selected"] = "selected"
        self.add_element("option",attrs=attrs).add_text(option_label)
