# MIT License
#
# Copyright (C) 2023-2024 University of Reading
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software
# and associated documentation files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import numpy as np
import xarray as xr
import os
import datashader as dsh
import datashader.transfer_functions as tf
from datashader import reductions as rd
import logging
import json
import math
from PIL import Image, ImageFont, ImageDraw

class CMap:

    def __init__(self, colors, vmin, vmax):
        self.colors = colors
        self.vmin = vmin
        self.vmax = vmax

    def get_rgb(self,name,vmin,vmax,v):
        lookup_v = (v - vmin) / (vmax-vmin)

        ncols = len(self.colors)
        index = math.floor(lookup_v*ncols)
        if index < 0:
            index = 0

        if index >= ncols:
            index = ncols-1

        return self.colors[index]

    def get_colors(self):
        return self.colors


class BigPlot:

    def __init__(self, data_array, x="x", y="Y", vmin=0, vmax=1, vformat="%02f", cmap_name="viridis", title="",  output_path="output.png", subtexts=[], legend_width=300, legend_height=50, plot_width=1800, flip=True, theight=50,
                 subtheight=25, selectors={}, iselectors={}, font_path=None, border=20,  cchart=None, gamma=0.5):
        self.logger = logging.getLogger("BigPlot")
        self.data_array:xr.DataArray = data_array
        self.x = x
        self.y = y
        self.vmin = vmin
        self.vmax = vmax
        self.vformat = vformat
        self.cmap_name = cmap_name
        self.legend_width = legend_width
        self.legend_height = legend_height
        self.title = title
        self.output_path = output_path
        self.subtexts = subtexts
        self.plot_width = plot_width
        self.flip = flip
        self.theight = theight
        self.subtheight = subtheight
        self.cmap_colors = []
        self.cmap = None
        self.cchart = cchart
        self.gamma = gamma
        self.selectors = selectors
        self.iselectors = iselectors
        self.font_path = font_path if font_path else os.path.join(os.path.split(__file__)[0],"..","misc","Roboto-Black.ttf")
        self.border = border
        if "rgb" not in self.data_array.dims:
            cmap_path = os.path.join(os.path.split(__file__)[0], "..", "misc", "cmaps", self.cmap_name + ".json")
            with open(cmap_path) as f:
                o = json.loads(f.read())
                for rgb in o:
                    r = int(255*rgb[0])
                    g = int(255*rgb[1])
                    b = int(255*rgb[2])
                    self.cmap_colors.append(f"#{r:02X}{g:02X}{b:02X}")
                self.cmap = CMap(o,self.vmin,self.vmax)

    def run(self):
        da = self.data_array

        if self.selectors:
            da = da.sel(**self.selectors)

        if self.iselectors:
            da = da.isel(**self.iselectors)

        da = da.squeeze()

        if len(da.shape) > 3:
            self.logger.error(f"too many dimensions to plot {da.dims}")
            return
        if len(da.shape) < 2:
            self.logger.error(f"too few dimensions to plot {da.dims}")
            return

        h = da.shape[da.dims.index(self.y)]
        w = da.shape[da.dims.index(self.x)]

        plot_height = int(self.plot_width*(h/w))
        cvs = dsh.Canvas(plot_width=self.plot_width, plot_height=plot_height,
                    x_range=(float(da[self.x].min()), float(da[self.x].max())),
                    y_range=(float(da[self.y].min()), float(da[self.y].max())))

        if len(da.shape) == 2:
            if not self.flip:
                da = da.isel(**{self.y: slice(None, None, -1)})
            if self.cchart is not None:
                agg = cvs.raster(da.squeeze(), agg=rd.mode, interpolate='nearest')
                shaded = tf.shade(agg, color_key=self.cchart)
            else:
                da = xr.where(da < self.vmin, np.nan, da)
                da = xr.where(da > self.vmax, np.nan, da)
                agg = cvs.raster(da.squeeze(), agg=rd.first, interpolate='linear')
                shaded = tf.shade(agg, cmap=self.cmap_colors,
                          how="linear",
                          span=(self.vmin, self.vmax))
            p = shaded.to_pil()
        else:
            if self.flip:
                da = da.isel(**{self.y: slice(None, None, -1)})
            agg = cvs.raster(da)
            alist = []
            a = None
            for cindex in range(0,3):
                arr = agg[cindex,:,:].squeeze().data
                m = (~np.isnan(arr)*255).astype(np.uint8) # 0 = transparent, 1=visible
                if a is None:
                    # define transparency if the first channel is NaN
                    a = m
                else:
                    # if subsequent channels are NaN, make pixels transparent
                    a = np.minimum(a,m)
                v = (arr - self.vmin) / (self.vmax - self.vmin)
                v = np.power(v,self.gamma) # juice up the contrast with gamma correction
                v = (255 * v)
                v = np.where(v > 255, 255, v)
                v = np.where(v < 0, 0, v)
                v = v.astype(np.uint8)
                alist.append(v)
            alist.append(a)
            arr = np.stack(alist, axis=-1)
            p = Image.fromarray(arr, mode="RGBA")

        font = ImageFont.truetype(self.font_path, size=self.theight)
        spacing = self.theight

        # work out the combined width and height of the whole plot
        combined_height = self.border
        if self.title:
            combined_height += self.theight+spacing
        combined_height += len(self.subtexts)*int(self.subtheight*1.5)
        if self.legend_height:
            combined_height += self.legend_height+spacing
        combined_height += plot_height+self.border
        combined_width = 2*self.border+self.plot_width

        combined = Image.new('RGBA', (combined_width, combined_height), "white")

        y = self.border
        draw = ImageDraw.Draw(combined)

        if self.title:
            draw.text((round(self.border+self.plot_width * 0.5),y), self.title, fill=(0, 0, 0), font=font, anchor="ma")
            y += self.theight+spacing

        if self.legend_height:
            lp = self.create_legend_image()
            legendfont = ImageFont.truetype(self.font_path, size=self.legend_height)
            combined.paste(lp, (round(self.border+self.plot_width * 0.5 - self.legend_width * 0.5), y))
            min_label = self.vformat % self.vmin
            max_label = self.vformat % self.vmax

            draw.text((round(combined_width * 0.5 - self.legend_width * 0.5) - 20, y), min_label, fill=(0,0,0), font=legendfont, anchor="rt")
            draw.text((round(combined_width * 0.5 + self.legend_width * 0.5) + 20, y), max_label, fill=(0,0,0), font=legendfont, anchor="lt")
            y += self.legend_height+spacing

        if self.subtexts:
            subfont = ImageFont.truetype(self.font_path, size=self.subtheight)
            for subtext in self.subtexts:
                draw.text((round(self.border + self.plot_width * 0.5), y), subtext, fill=(0, 0, 0), font=subfont,
                      anchor="ma")
                y += int(self.subtheight*1.5)

        combined.paste(p, (self.border, y))

        with open(self.output_path, "wb") as f:
            if self.output_path.endswith(".png"):
                format = "PNG"
            elif self.output_path.endswith(".pdf"):
                format = "PDF"
            elif self.output_path.endswith(".jpg") or self.output_path.endswith(".jpeg"):
                format = "JPEG"
            else:
                self.logger.error("Unsupported output file format, currently only pdf and png are supported")
                return
            combined.save(f, format=format)

        self.logger.info(f"Written {self.output_path}")

    def create_legend_image(self):
        lwidth = self.legend_width
        lheight = self.legend_height

        ldata = xr.DataArray(np.zeros((lheight, lwidth)), dims=("y", "x"))
        ldata["x"] = xr.DataArray(np.arange(0, lwidth), dims=("x",))
        ldata["y"] = xr.DataArray(np.arange(0, lheight), dims=("y",))

        for i in range(0, lwidth):
            v = self.vmin + i * (self.vmax - self.vmin) / lwidth
            ldata[:, i] = v

        lcvs = dsh.Canvas(plot_width=lwidth, plot_height=lheight,
                          x_range=(0, lwidth),
                          y_range=(0, lheight))

        lagg = lcvs.raster(ldata, agg=rd.first, interpolate='linear')

        lshaded = tf.shade(lagg, cmap=self.cmap_colors,
                           how="linear",
                           span=(self.vmin, self.vmax))
        return lshaded.to_pil()