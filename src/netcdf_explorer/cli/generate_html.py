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

import argparse
import os
import xarray as xr
import numpy as np
import logging
import yaml
import sys

from netcdf_explorer.api.html_generator import HTMLGenerator

def subset(ds, case_dimension, sample_count, sample_cases):
    n = len(ds[case_dimension])
    selected_indexes = list(range(n))

    if sample_cases:
        selected_indexes = sample_cases

    if sample_count and sample_count < n:
        selected_indexes = np.random.choice(np.array(selected_indexes), sample_count, replace=False).tolist()
    if sample_cases or sample_count:
        ds = ds.isel(**{case_dimension:selected_indexes})
    return ds, selected_indexes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", help="Set the title of the plot", required=True)
    parser.add_argument("--input-path", help="the netcdf4 file to visualise", required=True)
    parser.add_argument("--download-data", action="store_true",
                        help="include a download link in the HTML")
    parser.add_argument("--output-folder", help="folder to write html output", default="html_output")
    parser.add_argument("--config-path", help="JSON or YAML file specifying one or more layer specifications",
                        default="layers.json", required=True)
    parser.add_argument("--sample-count", type=int, default=None,
                        help="randomly sample this many cases for display"),
    parser.add_argument("--sample-cases", nargs="+", type=int, default=None,
                        help="display these sample cases (provide their indices, starting at 0)")
    parser.add_argument("--filter-controls", action="store_true",
                        help="add month filter controls to the overlay view")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    with open(args.config_path) as f:
        if args.config_path.endswith(".yml") or args.config_path.endswith(".yaml"):
            config = yaml.load(f, Loader=yaml.FullLoader)
        else:
            print("Error - config file should be yaml (.yml or .yaml) format")
            sys.exit(-1)
        dimensions = config.get("dimensions", {})
        case_dimension = dimensions.get("case", None)

    if case_dimension is None:
        print("Error - please provide a case dimension")
        sys.exit(-1)

    index_list = []

    print(f"Reading {args.input_path}")
    ds = xr.open_dataset(args.input_path)
    if case_dimension:
        ds, indices = subset(ds, case_dimension, sample_count=args.sample_count, sample_cases=args.sample_cases)
        for i in indices:
            index_list.append((args.input_path,i))

    download_filepath = None
    if args.download_data:
        download_filepath = args.input_path

    g = HTMLGenerator(config, ds, os.path.abspath(args.output_folder), title=args.title,
                                 download_from=download_filepath,
                                 filter_controls=args.filter_controls, index_list=index_list)
    g.run()


if __name__ == '__main__':
    main()
