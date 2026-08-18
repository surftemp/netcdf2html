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

import math
import os
import shutil
import requests
import json

from PIL import Image, ImageDraw
from matplotlib import cm
import numpy as np
import xarray as xr

from .data_encoder import DataEncoder

from .colours import colours_to_rgb, ColoursToRGB

def save_image(arr,vmin,vmax,path,cmap_name="coolwarm"):
    if not hasattr(cm,cmap_name):
        raise ValueError("Unknown colour map: " + cmap_name)
    cmap_fn = getattr(cm,cmap_name)
    im = Image.fromarray(np.uint8((255*cmap_fn((arr-vmin)/(vmax-vmin)))))
    im.save(path)

def save_image_falsecolour(data_red, data_green, data_blue, path, min_value=None, max_value=None, low_percentile=None, high_percentile=None, red_gamma=0.5, green_gamma=0.5, blue_gamma=0.5):
    alist = []

    combined = np.concatenate((data_red,data_green,data_blue))
    low_val = 0
    high_val = 1
    if min_value is not None or max_value is not None:
        if min_value is not None:
            low_val = min_value
        if max_value is not None:
            high_val = max_value
    elif low_percentile is not None or high_percentile is not None:
        if low_percentile is None:
            low_percentile = 0
        if high_percentile is None:
            high_percentile = 100
        low_val, high_val = np.nanpercentile(combined, [low_percentile, high_percentile])
    for (arr,gamma) in [(data_red,red_gamma),(data_green,green_gamma),(data_blue,blue_gamma)]:
        v = np.clip(arr, low_val, high_val)
        v = (v - low_val) / (high_val - low_val)
        v = np.where(np.isnan(v), np.nan, np.power(np.where(np.isnan(v),0,v), gamma))
        # convert to pixel values
        v = v * 255
        v = np.where(np.isnan(v),0, v)
        alist.append(v.astype(np.uint8))
    arr = np.stack(alist,axis=-1)
    im = Image.fromarray(arr)
    im.save(path)

def save_image_mask(arr, path, r, g, b):
    alist = []
    a = np.zeros(arr.shape)
    alist.append((a + r).astype(np.uint8))
    alist.append((a + g).astype(np.uint8))
    alist.append((a + b).astype(np.uint8))
    alist.append(np.where(arr>0,255,0).astype(np.uint8))
    rgba_arr = np.stack(alist, axis=-1)
    im = Image.fromarray(rgba_arr)
    im.save(path)

def save_image_discrete(arr,path,values):
    lookup = {}
    for (k,v) in values.items():
        (label,colour) = v
        if not isinstance(k,str):
            k = int(k)
        lookup[k] = ColoursToRGB.lookup(colour)+[255]

    def get_rgba(value):
        if isinstance(value,str):
            key = value
        else:
            key = int(value) if not math.isnan(value) else -1
        if key not in lookup:
            return np.array([0,0,0,255])
        else:
            return np.array(lookup[key])

    im = Image.fromarray(np.uint8((np.vectorize(get_rgba,signature='()->(n)')(arr))),mode="RGBA")
    im.save(path)

class LayerGroup:

    def __init__(self, layer, converter, layer_name, layer_label, sublayers):
        self.layer = layer
        self.converter = converter
        self.layer_name = layer_name
        self.layer_label = layer_label
        self.sublayers = sublayers
        self.grid_view = False
        self.overlay_view = False

    def set_grid_view(self, grid_view):
        self.grid_view = grid_view

    def get_grid_view(self):
        return self.grid_view

    def set_overlay_view(self, overlay_view):
        self.overlay_view = overlay_view

    def get_overlay_view(self):
        return self.overlay_view

    def has_legend(self):
        return self.sublayers[0].has_legend()

    def build_legend(self, path):
        return self.sublayers[0].build_legend(path)

    def check(self, ds):
        remove_layers = []
        for layer in self.sublayers:
            err = layer.check(ds)
            if err:
                self.converter.logger.warning(f"Unable to add layer {layer.layer_name}: {err}")
                remove_layers.append(layer)

        for layer in remove_layers:
            self.sublayers.remove(layer)

        if len(self.sublayers) == 0:
            return "No valid layers in this group"

    def build(self,ds,path):
        for layer in self.sublayers:
            layer.build(ds,path)

    def save_data(self):
        return False

    def get_layers(self):
        return self.sublayers

    def get_sublayers(self):
        return self.sublayers

class LayerBase:

    def __init__(self, layer, converter, layer_name, layer_label, selectors={}):
        self.layer_name = layer_name
        self.layer_label = layer_label
        self.case_dimension = ""
        self.x_coordinate = ""
        self.y_coordinate = ""
        self.case_dimension = ""
        self.selectors = selectors
        self.flipud = False
        self.fliplr = False
        self.converter = converter
        self.case_dimension = layer.get("dimensions",{}).get("case",converter.case_dimension)
        self.x_dimension = layer.get("dimensions",{}).get("x",converter.x_dimension)
        self.y_dimension = layer.get("dimensions",{}).get("y",converter.y_dimension)
        self.time_coordinate = layer.get("coordinates",{}).get("time",converter.time_coordinate)
        self.x_coordinate = layer.get("coordinates",{}).get("x",converter.x_coordinate)
        self.y_coordinate = layer.get("coordinates",{}).get("y",converter.y_coordinate)
        self.group = None
        self.case_wise = False
        self.grid_view = False
        self.overlay_view = False

    def set_group(self, group):
        self.group = group

    def get_group(self):
        return self.group

    def set_case_wise(self, is_case_wise):
        self.case_wise = is_case_wise

    def get_case_wise(self):
        return self.case_wise

    def set_grid_view(self, grid_view):
        self.grid_view = grid_view

    def get_grid_view(self):
        return self.grid_view

    def set_overlay_view(self, overlay_view):
        self.overlay_view = overlay_view

    def get_overlay_view(self):
        return self.overlay_view

    def check(self, ds):
        for variable in [self.x_coordinate, self.y_coordinate, self.time_coordinate]:
            if variable and variable not in ds:
                return f"No variable {variable}"
        xc = self.converter.get_x_coords(ds)
        yc = self.converter.get_y_coords(ds)
        if len(xc.shape) != 1:
            return "x_coordinate {self.x_coordinate} must be 1-dimensional"
        if len(yc.shape) != 1:
            return "y_coordinate {self.y_coordinate} must be 1-dimensional"

        if float(xc.data[0]) > float(xc.data[-1]):
            self.fliplr = True
        if float(yc.data[0]) < float(yc.data[-1]):
            self.flipud = True

    def get_data(self, da):
        if self.selectors:
            da = da.isel(**self.selectors)
        da = da.squeeze()
        ndims = len(da.dims)

        # make x and y coordinates 2D if they are 1D
        if ndims == 1:
            shape = (self.converter.data_height, self.converter.data_width)
            if da.dims[0] == self.converter.y_dimension:
                da = xr.DataArray(
                    np.broadcast_to(da.data[None].T, shape),
                    dims=(self.converter.y_dimension, self.converter.x_dimension))
            elif da.dims[0] == self.converter.x_dimension:
                da = xr.DataArray(
                    np.broadcast_to(da.data, shape), dims=(self.converter.y_dimension, self.converter.x_dimension))
            ndims = len(da.dims)
        if ndims != 2:
            raise Exception(f"Data for layer {self.layer_name} is not 2D")

        x_index = da.dims.index(self.x_dimension)
        y_index = da.dims.index(self.y_dimension)
        arr = da.data
        if y_index > x_index:
            arr = np.transpose(arr)
        if self.flipud:
            arr = np.flipud(arr)
        if self.fliplr:
            arr = np.fliplr(arr)
        return arr

    def save_data(self):
        return False

    def get_sublayers(self):
        return None


class LayerRGB(LayerBase):

    def __init__(self, layer, converter, layer_name, layer_label, selectors, red_variable, green_variable, blue_variable,
                 red_gamma=0.5, green_gamma=0.5, blue_gamma=0.5, min_value=None, max_value=None, low_percentile=None, high_percentile=None):
        super().__init__(layer, converter, layer_name, layer_label, selectors)
        self.red_variable = red_variable
        self.green_variable = green_variable
        self.blue_variable = blue_variable
        self.red_gamma = red_gamma
        self.green_gamma = green_gamma
        self.blue_gamma = blue_gamma
        self.min_value = min_value
        self.max_value = max_value
        self.low_percentile = low_percentile
        self.high_percentile = high_percentile

    def has_legend(self):
        return False

    def check(self, ds):
        err = super().check(ds)
        if err:
            return err
        for variable in [self.red_variable, self.green_variable, self.blue_variable]:
            if variable not in ds:
                return f"No variable {variable}"
            if self.converter.case_dimension and self.converter.case_dimension in ds[variable].dims:
                self.set_case_wise(True)

    def build(self,ds,path):
        red = self.get_data(ds[self.red_variable])
        green = self.get_data(ds[self.green_variable])
        blue = self.get_data(ds[self.blue_variable])
        save_image_falsecolour(red, green, blue, path, red_gamma=self.red_gamma,
                               green_gamma=self.green_gamma, blue_gamma=self.blue_gamma,
                               min_value=self.min_value, max_value=self.max_value,
                               low_percentile=self.low_percentile, high_percentile=self.high_percentile)


class LayerSingleBand(LayerBase):

    def __init__(self, layer, converter, layer_name, layer_label, selectors, band_name, vmin, vmax, cmap_name, data):
        super().__init__(layer, converter, layer_name, layer_label, selectors)
        self.band_name = band_name
        self.vmin = vmin
        self.vmax = vmax
        self.cmap_name = cmap_name
        self.data = data

    def get_cmap(self):
        return self.cmap_name

    def check(self, ds):
        err = super().check(ds)
        if err:
            return err
        if self.band_name not in ds:
            return f"No variable {self.band_name}"
        if self.converter.case_dimension and self.converter.case_dimension in ds[self.band_name].dims:
            self.set_case_wise(True)

    def build(self,ds,path):
        save_image(self.get_data(ds[self.band_name]), self.vmin, self.vmax, path, self.cmap_name)

    def has_legend(self):
        return True

    def build_legend(self, path):
        legend_width, legend_height = 200, 20
        a = np.zeros(shape=(legend_height,legend_width))
        for i in range(0,legend_width):
            a[:,i] = self.vmin + (i/legend_width) * (self.vmax-self.vmin)
        save_image(a, self.vmin, self.vmax, path, self.cmap_name)

    def save_data(self):
        return self.data is not None

    def build_data(self,ds,path):
        de = DataEncoder()
        de.encode(self.get_data(ds[self.band_name]), path)
        return self.data

class LayerVector(LayerBase):

    def __init__(self, layer, converter, layer_name, layer_label, selectors, band_name, scale, thickness, colour):
        super().__init__(layer, converter, layer_name, layer_label, selectors)
        self.band_name = band_name
        self.scale = scale
        self.thickness = thickness
        self.colour = colour

    def check(self, ds):
        err = super().check(ds)
        if err:
            return err
        if self.band_name not in ds:
            return f"No variable {self.band_name}"
        if self.converter.case_dimension and self.converter.case_dimension in ds[self.band_name].dims:
            self.set_case_wise(True)

    def build(self,ds,path):
        s = ds[self.band_name].item()
        vectors = json.loads(s)

        image_width, image_height = self.converter.get_image_dimensions(ds)

        image_width *= self.scale
        image_height *= self.scale

        im = Image.new('RGBA', (image_width, image_height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(im)

        def swap_xy(v):
            return [((x+0.5)*self.scale,image_height-(y+0.5)*self.scale) for (y,x) in v]

        for vector in vectors:
            draw.line(swap_xy(vector), fill=tuple(self.colour), width=self.thickness)
        im.save(path)

    def has_legend(self):
        return False

    def build_legend(self, path):
        pass

    def save_data(self):
        return False

    def build_data(self,ds,path):
        pass


class LayerWMS(LayerBase):

    def __init__(self, layer, converter, layer_name, layer_label, wms_url, scale):
        super().__init__(layer, converter, layer_name, layer_label)
        self.wms_url = wms_url
        self.cache = {}
        self.failed = set()
        self.scale = scale

    def check(self, ds):
        err = super().check(ds)
        if err:
            return err
        if self.converter.case_dimension and self.converter.case_dimension in ds[self.converter.x_coordinate].dims \
                or self.converter.case_dimension in ds[self.converter.y_coordinate].dims:
            self.set_case_wise(True)

    def has_legend(self):
        return False

    def get_bounds(self,ds):
        xc = self.converter.get_x_coords(ds)
        yc = self.converter.get_y_coords(ds)

        spacing_x = abs(float(xc[0]) - float(xc[1]))
        spacing_y = abs(float(yc[0]) - float(yc[1]))

        x_min = float(xc.min()) - spacing_x/2
        x_max = float(xc.max()) + spacing_x/2
        y_min = float(yc.min()) - spacing_y/2
        y_max = float(yc.max()) + spacing_y/2
        return ((x_min,y_min),(x_max,y_max))

    def build(self,ds,path):
        if os.path.exists(path):
            os.remove(path)
        image_width, image_height = self.converter.get_image_dimensions(ds)
        image_width *= self.scale
        image_height *= self.scale

        ((x_min, y_min), (x_max, y_max)) = self.get_bounds(ds)

        url = self.wms_url.replace("{WIDTH}",str(image_width)).replace("{HEIGHT}",str(image_height)) \
            .replace("{YMIN}",str(y_min)).replace("{YMAX}",str(y_max)) \
            .replace("{XMIN}",str(x_min)).replace("{XMAX}", str(x_max))

        if url in self.cache:
            shutil.copyfile(self.cache[url],path)
        elif url in self.failed:
            pass
        else:
            r = requests.get(url, stream=True)
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    r.raw.decode_content = True
                    shutil.copyfileobj(r.raw, f)
                self.cache[url] = path
            else:
                self.failed.add(url)

class LayerMask(LayerBase):

    def __init__(self, layer, converter, layer_name, layer_label, selectors, band_name, r, g, b):
        super().__init__(layer, converter, layer_name, layer_label, selectors)
        self.band_name = band_name
        self.r = r
        self.g = g
        self.b = b

    def has_legend(self):
        return False

    def check(self, ds):
        err = super().check(ds)
        if err:
            return err
        if self.band_name not in ds:
            return f"No variable {self.band_name}"
        if self.converter.case_dimension and self.converter.case_dimension in ds[self.band_name].dims:
            self.set_case_wise(True)

    def build(self,ds,path):
        save_image_mask(self.get_data(ds[self.band_name].astype(int)), path, self.r, self.g, self.b)

class LayerDiscrete(LayerBase):

    def __init__(self, layer, converter, layer_name, layer_label, selectors, band_name, values):
        super().__init__(layer, converter, layer_name, layer_label, selectors)
        self.band_name = band_name
        self.values = values

    def check(self, ds):
        err = super().check(ds)
        if err:
            return err
        if self.band_name not in ds:
            return f"No variable {self.band_name}"
        for (k,v) in self.values.items():
            (label,color) = v
            rgb = ColoursToRGB.lookup(color)
            if rgb is None:
                return f"Invalid colour {color}"
        if self.converter.case_dimension and self.converter.case_dimension in ds[self.band_name].dims:
            self.set_case_wise(True)

    def build(self,ds,path):
        save_image_discrete(self.get_data(ds[self.band_name]), path, self.values)

    def has_legend(self):
        return False

class LayerStaticImage(LayerBase):

    def __init__(self, layer, converter, layer_name, layer_label, selectors, image_path):
        super().__init__(layer, converter, layer_name, layer_label, selectors)
        self.image_path = image_path

    def has_legend(self):
        return False

    def check(self, ds):
        return None

    def build(self,ds,path):
        shutil.copyfile(self.image_path, path)

class LayerFactory:

    @staticmethod
    def create(converter, layer_name, layer, in_layer_group=False):
        layer_type = layer["type"]
        layer_label = layer.get("label", layer_name)
        selectors = layer.get("selectors", {})
        grid_view = layer.get("grid_view", True)
        overlay_view = layer.get("overlay_view", True)
        if layer_type == "layer_group":
            if in_layer_group:
                raise Exception("Cannot nest layer groups")
            sublayers = []
            for (sublayer_name, sublayer) in layer.get("layers",{}).items():
                sublayers.append(LayerFactory.create(converter,layer_name+"_"+sublayer_name,sublayer,in_layer_group=True))
            if len(sublayers) == 0:
                raise Exception("Layer group should contain at least one layer")
            created_layer = LayerGroup(layer, converter, layer_name, layer_label, sublayers)
            for sublayer in sublayers:
                sublayer.set_group(created_layer)
        elif layer_type == "single":
            layer_band = layer.get("band", layer_name)
            vmin = layer["min_value"]
            vmax = layer["max_value"]
            cmap = layer.get("cmap", "coolwarm")
            data = layer.get("data", None)
            created_layer = LayerSingleBand(layer, converter, layer_name, layer_label, selectors, layer_band, vmin, vmax, cmap, data)
        elif layer_type == "mask":
            layer_band = layer.get("band", layer_name)
            if "colour" in layer:
                colour = layer["colour"]
                if colour in colours_to_rgb:
                    rgb = colours_to_rgb[layer["colour"]]
                    r = rgb["r"]
                    g = rgb["g"]
                    b = rgb["b"]
                else:
                    raise Exception(f"Unknown colour {colour}")
            else:
                r = layer.get("r",0)
                g = layer.get("g",0)
                b = layer.get("b",0)

            created_layer = LayerMask(layer, converter, layer_name, layer_label, selectors, layer_band, r, g, b)
        elif layer_type == "rgb":
            red_band = layer["red_band"]
            green_band = layer["green_band"]
            blue_band = layer["blue_band"]
            red_gamma = layer.get("red_gamma",0.5)
            green_gamma = layer.get("green_gamma",0.5)
            blue_gamma = layer.get("blue_gamma",0.5)
            min_value = layer.get("min_value")
            max_value = layer.get("max_value")
            low_percentile = layer.get("low_percentile")
            high_percentile = layer.get("high_percentile")
            created_layer = LayerRGB(layer, converter, layer_name, layer_label, selectors, red_variable=red_band,
                    green_variable=green_band, blue_variable=blue_band,
                    red_gamma=red_gamma, green_gamma=green_gamma, blue_gamma=blue_gamma,
                    min_value=min_value, max_value=max_value,
                    low_percentile=low_percentile, high_percentile=high_percentile)
        elif layer_type == "discrete":
            layer_band = layer.get("band", layer_name)
            values = layer["values"]
            created_layer = LayerDiscrete(layer, converter, layer_name, layer_label, selectors, layer_band, values)
        elif layer_type == "wms":
            url = layer["url"]
            scale = layer.get("scale", 1)
            created_layer = LayerWMS(layer, converter, layer_name, layer_label, url, scale)
        elif layer_type == "vector":
            layer_band = layer.get("band", layer_name)
            scale = layer.get("scale", 10)
            thickness = layer.get("thickness", 3)
            colour = layer.get("colour",[0,0,0,255])
            created_layer = LayerVector(layer, converter, layer_name, layer_label, selectors, layer_band, scale=scale, thickness=thickness,colour=colour)
        elif layer_type == "static_image":
            image_path = layer.get("image_path")
            created_layer = LayerStaticImage(layer, converter, layer_name, layer_label, selectors, image_path)
        else:
            raise Exception(f"Unknown layer type {layer_type}")
        if not in_layer_group:
            created_layer.set_grid_view(grid_view)
            created_layer.set_overlay_view(overlay_view)
        return created_layer


