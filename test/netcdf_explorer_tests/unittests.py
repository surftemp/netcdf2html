import unittest
import os
import xarray as xr
import yaml
import json

import netcdf_explorer.api.bigplot
from netcdf_explorer.api.html_generator import HTMLGenerator

class Test(unittest.TestCase):

    def test_293_api(self):
        path = os.path.join(os.path.split(__file__)[0],"area_293_min.nc")
        ds = xr.open_dataset(path)
        layers_path = os.path.join(os.path.split(__file__)[0],"example_layers.yaml")
        output_folder = os.path.join(os.path.split(__file__)[0], "area_293_output_api")
        with open(layers_path) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        gen = HTMLGenerator(config=config, input_ds=ds, output_folder=output_folder, title="area 293", download_from=path, filter_controls=True)
        gen.run()

    def test_293_commandline(self):
        cli_test = 'python -m netcdf_explorer.cli.generate_html --input-path area_293_min.nc --title "area_293" --output-folder area_293_output_cli --config-path example_layers.yaml --download-data'
        os.system(f'(cd {os.path.split(__file__)[0]}; {cli_test})')

    def test_bigplot(self):
        path = os.path.join(os.path.split(__file__)[0], "area_293_min.nc")
        output_path = os.path.join(os.path.split(__file__)[0], "area_293_min.png")
        ds = xr.open_dataset(path).isel(time=1)

        da_red = ds["B2"]
        da_green = ds["B3"]
        da_blue = ds["B4"]
        da = xr.concat([da_red, da_green, da_blue], dim="band")

        bp = netcdf_explorer.api.bigplot.BigPlot(da, x="x", y="y", vmin=0, vmax=1, legend_height=0, output_path=output_path,plot_width=1024)
        bp.run()

    def test_bigplot_commandline(self):
        cli_test = 'python -m netcdf_explorer.cli.bigplot --input-path area_293_min.nc --iselector time 1 1 --input-variable B2 B3 B4 --output-path area_293_min_cmdline.png --title "area_293_min" --vmin 0 --vmax 0.3 --plot-width 512'
        os.system(f'(cd {os.path.split(__file__)[0]}; {cli_test})')

    def test_bigplot_commandline_st(self):
        cli_test = 'python -m netcdf_explorer.cli.bigplot --input-path area_293_min.nc --iselector time 1 1 --input-variable ST --output-path area_293_min_cmdline_st.png --title "area_293_min_st" --vmin 270 --vmax 330 --cmap viridis --plot-width 512'
        os.system(f'(cd {os.path.split(__file__)[0]}; {cli_test})')


