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

from ..htmlfive.html5_builder import ElementFragment

class LegendFragment(ElementFragment):

    def __init__(self, title,image_fragement, v_min=None, v_max=None):
        super().__init__("div", {}, {})
        self.add_element("p").add_text(title)
        label = ""
        if v_min is not None:
            label += "min="+str(v_min) + " "
        if v_max is not None:
            label += "max=" + str(v_max) + " "
        if label:
            self.add_element("div").add_text(label)
        self.add_fragment(image_fragement)







