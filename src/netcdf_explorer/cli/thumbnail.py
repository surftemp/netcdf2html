# MIT License
#
# Copyright (c) 2023-2024 University of Reading
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import json

import xarray as xr

import datashader as dsh
import datashader.transfer_functions as tf
from datashader import reductions as rd

from PIL import Image

class Thumbnail:

    def __init__(self, variable, cmap, vmin, vmax, x_coord, y_coord, plot_width, background_image_path=None, background_alpha=0.2,
                 selector={}):
        self.variable = variable
        self.background_image_path = background_image_path
        self.background_alpha = background_alpha
        self.vmin = vmin
        self.vmax = vmax
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.plot_width = plot_width
        self.selector = selector

        self.cmap_colours = []

        cmaps_folder = os.path.join(os.path.split(__file__)[0], "..", "misc", "cmaps")

        # get a consistent lower case based cmap lookup
        self.cmaps_paths = {}
        for filename in os.listdir(cmaps_folder):
            if filename.endswith(".json"):
                self.cmaps_paths[os.path.splitext(filename)[0].lower()] = filename

        reverse_cmap = False
        if cmap.endswith("_r"):
            cmap = cmap[:-2]
            reverse_cmap = True

        cmap_path = os.path.join(cmaps_folder, self.cmaps_paths[cmap.lower()])

        with open(cmap_path) as f:
            o = json.loads(f.read())
            for rgb in o:
                r = int(255 * rgb[0])
                g = int(255 * rgb[1])
                b = int(255 * rgb[2])
                self.cmap_colours.append(f"#{r:02X}{g:02X}{b:02X}")

        if reverse_cmap:
            self.cmap_colours.reverse()

    def generate(self, dataset, output_path):
        da = dataset[self.variable]
        if (self.selector):
            da = da.isel(**self.selector)
        da = da.squeeze()

        if len(da.shape) != 2:
            raise Exception(f"too many dimensions to plot {da.dims}")

        if dataset[self.y_coord].data[0].item() > dataset[self.y_coord].data[1].item():
            y_dim = da.dims[0]
            da = da.isel(**{y_dim: slice(None, None, -1)})

        h = da.shape[0]
        w = da.shape[1]

        plot_height = int(self.plot_width * (h / w))
        cvs = dsh.Canvas(plot_width=self.plot_width, plot_height=plot_height,
                         x_range=(float(da[self.x_coord].min()), float(da[self.x_coord].max())),
                         y_range=(float(da[self.y_coord].min()), float(da[self.y_coord].max())))

        agg = cvs.raster(da.squeeze(), agg=rd.first, interpolate='linear')

        shaded = tf.shade(agg, cmap=self.cmap_colours,
                          how="linear",
                          span=(self.vmin, self.vmax))

        p = shaded.to_pil()

        if self.background_image_path:
            back = Image.open(self.background_image_path)
            back = back.resize(p.size)
            p = Image.blend(p, back, self.background_alpha)

        with open(output_path, "wb") as f:
            p.save(f, format="PNG")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", help="path of netcdf input file", required=True)
    parser.add_argument("--output-path", help="path of output png file", required=True)
    parser.add_argument("--input-variable",
                        help="name of variable to plot.", required=True)
    parser.add_argument("--x", help="name of x coord", default="x")
    parser.add_argument("--y", help="name of y coord", default="y")

    parser.add_argument("--iselector", nargs=3, help="provide a dimension selector",
                        metavar=("dimension", "min", "max"),
                        action="append")

    parser.add_argument("--vmin", type=float, help="minimum input variable value to use in colour scale", default=0)
    parser.add_argument("--vmax", type=float, help="maximum input variable value to use in colour scale", default=1)

    parser.add_argument("--cmap", help="colour scale to use, should be the  name of a matplotlib color map",
                        default="turbo")

    parser.add_argument("--background-image-path", help="optional - path to a background image onto which the plot is overlaid",
                        default=None)


    parser.add_argument("--background-image-alpha", help="optional - alpha transparency for the background image",
                        default=0.2)


    parser.add_argument("--plot-width", help="Width of the main image plot, in pixels", type=int, default=1024)

    args = parser.parse_args()

    iselectors = {}

    if args.iselector:
        for (dimension, min, max) in args.iselector:
            iselectors[dimension] = range(int(min), int(max) + 1)

    t = Thumbnail(variable=args.input_variable,
                  vmin=args.vmin, vmax=args.vmax,
                  x_coord=args.x, y_coord=args.y,
                  cmap=args.cmap,
                  plot_width=args.plot_width,
                  selector=iselectors,
                  background_image_path=args.background_image_path,
                  background_alpha=args.background_image_alpha)

    ds = xr.open_dataset(args.input_path)
    t.generate(ds, args.output_path)

if __name__ == '__main__':
    main()