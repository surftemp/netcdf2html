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

import json
import glob
import os.path
import sys
import logging

import xarray as xr

from netcdf_explorer.api.bigplot import BigPlot

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", nargs="+", help="path matching one or more netcdf input file(s)", required=True)
    parser.add_argument("--input-variable", help="name of variable(s) to plot.  Supply either one variable or three variables (red,green,blue)", nargs="+", required=True)
    parser.add_argument("--x", help="name of x dimension", default="x")
    parser.add_argument("--y", help="name of y dimension", default="y")
    parser.add_argument("--selector", nargs=3, help="provide a coordinate selector", metavar=("coordinate","min","max"), action="append")
    parser.add_argument("--iselector", nargs=3, help="provide a dimension selector", metavar=("dimension", "min", "max"),
                        action="append")
    parser.add_argument("--flip", help="whether to flip the image upside down", action="store_true")
    parser.add_argument("--vmin", type=float, help="minimum input variable value to use in colour scale", default=0)
    parser.add_argument("--vmax", type=float, help="maximum input variable value to use in colour scale", default=1)
    parser.add_argument("--vformat", help="format to use when printing values", default="%0.0f")
    parser.add_argument("--cmap", help="colour scale to use, should be the  name of a matplotlib color map", default="turbo")

    parser.add_argument("--cchart", metavar="PATH", help="path to a JSON format {<value>:<colour>} colour chart mapping nominal values to colours, overrides --cmap if specified", default=None)
    parser.add_argument("--legend-width", help="width of the legend in pixels", type=int, default=100)
    parser.add_argument("--legend-height", help="height of the legend in pixels", type=int, default=50)

    parser.add_argument("--gamma", metavar="COEFFICIENT", help="coefficient to use for gamma correction in rgb plots", default=0.5)

    parser.add_argument("--title", help="A title for the plot")
    parser.add_argument("--title-height", help="Height of title in pixels", type=int, default=50)
    parser.add_argument("--attrs", help="Display these attributes from the file under the title", nargs="+", default=[])
    parser.add_argument("--attr-height", help="Height of attribute text", type=int, default=25)
    parser.add_argument("--font-path", help="Path to a true-type (.ttf) font to use (defaults to Roboto)", default=None)
    parser.add_argument("--output-path", help="Path to an output folder or filename", default=".")
    parser.add_argument("--output-filetype", help="output filetype (pdf or png)", default="png")
    parser.add_argument("--plot-width", help="Width of the main image plot, in pixels", type=int, default=1024)
    parser.add_argument("--border", help="Width of border around edge of the plot, in pixels", type=int, default=20)

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("main")

    args = parser.parse_args()

    selectors = {}
    iselectors = {}

    if args.selector:
        for (coordinate, min, max) in args.selector:
            selectors[coordinate] = slice(float(min),float(max))

    if args.iselector:
        for (dimension, min, max) in args.iselector:
            iselectors[dimension] = range(int(min), int(max)+1)

    input_paths = []
    for input_path in args.input_path:
        input_paths += glob.glob(input_path, recursive=True)

    npaths = len(input_paths)
    logger.info(f"Matched {npaths} input files to process")

    # --input-path may point to a path or a folder

    # if --input-path points to a folder, assign this variable
    output_folder = None

    # check the output path is not a filename
    suffix = os.path.splitext(args.output_path)[1]
    if suffix != "":
        # has suffix, looks like a filename?
        if npaths > 1:
            logger.error(f"When processing multiple input files, the --output-path should specify a folder")
            sys.exit(-1)
        else:
            # special case - for backwards compatibility allow args.output_path to point to a filename and not a folder
            if suffix not in [".pdf", ".png"]:
                logger.error(f"--output-path suffix {suffix} is not .pdf or .png")
                sys.exit(-1)
    else:
        # no suffix, looks like a folder?
        output_folder = args.output_path
        os.makedirs(output_folder,exist_ok=True)

    for input_path in input_paths:
        logger.info(f"Processing {input_path}")
        try:
            ds = xr.open_dataset(input_path)
            flip = args.flip
            if not flip:
                # look for y-coordinates to autodetect flipping
                for cname in ds.coords:
                    coords = ds.coords[cname]
                    if coords.attrs.get("standard_name","") == "projection_y_coordinate":
                        if ds[cname].data[0].item() < ds[cname].data[1].item():
                            # flip so y coordinates are descending
                            flip = True

            if len(args.input_variable) > 1:
                if len(args.input_variable) == 3:
                    da = xr.concat([ds[args.input_variable[0]],ds[args.input_variable[1]],ds[args.input_variable[2]]],dim="rgb")
                    args.legend_height = 0 # this will turn off the legend
                else:
                    logger.error("Please specify either 1 or 3 input variables")
                    sys.exit(-1)
            else:
                da = ds[args.input_variable[0]]

            subtexts = []
            for attr in args.attrs:
                if attr in ds.attrs:
                    subtexts.append(f"{attr}: {ds.attrs[attr]}")

            if output_folder is not None:
                input_filename = os.path.split(input_path)[-1]
                input_fileroot = os.path.splitext(input_filename)[0]
                output_path = os.path.join(output_folder,input_fileroot+"."+args.output_filetype)
            else:
                output_path = args.output_path

            legend_width = args.legend_width
            legend_height = args.legend_height

            cchart = None
            if args.cchart is not None:
                # cchart defines a nominal mapping from values to colours
                with open(args.cchart) as f:
                    input_cchart = json.loads(f.read())
                    # input is JSON format, need to convert keys from strings to floats
                    cchart = {float(key): value for key, value in input_cchart.items()}
                    legend_height = 0  # switch off legend for a nomimal colour mapping

            bp = BigPlot(data_array=da,
                         x=args.x, y=args.y, vmin=args.vmin, vmax=args.vmax, vformat=args.vformat,
                         cmap_name=args.cmap, cchart=cchart, gamma=args.gamma,
                         legend_width=legend_width, legend_height=legend_height,
                         title=args.title, subtexts=subtexts, theight=args.title_height, subtheight=args.attr_height,
                         output_path=output_path, plot_width=args.plot_width, flip=flip,
                         selectors=selectors, iselectors=iselectors, font_path=args.font_path)
            bp.run()
            ds.close()
        except Exception:
            logger.exception(f"Failed to process {input_path}")




if __name__ == '__main__':
    main()