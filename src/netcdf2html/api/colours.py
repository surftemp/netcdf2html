# -*- coding: utf-8 -*-

colours_to_rgb = {
    "violet": { "r": 238, "g": 130, "b": 238 },
    "magenta": { "r": 255, "g": 0, "b": 255 },
    "purple": { "r": 128, "g": 0, "b": 128 },
    "indigo": { "r": 75, "g": 0, "b": 130 },
    "pink": { "r": 255, "g": 192, "b": 203 },
    "crimson": { "r": 220, "g": 20, "b": 60 },
    "darkred": { "r": 139, "g": 0, "b": 0 },
    "red": { "r": 255, "g": 0, "b": 0 },
    "darkorange": { "r": 255, "g": 140, "b": 0 },
    "orange": { "r": 255, "g": 165, "b": 0 },
    "yellow": { "r": 255, "g": 255, "b": 0 },
    "lightyellow": { "r": 255, "g": 255, "b": 224 },
    "gold": { "r": 255, "g": 215, "b": 0 },
    "brown": { "r": 165, "g": 42, "b": 42 },
    "lightgreen": { "r": 144, "g": 238, "b": 144 },
    "green": { "r": 0, "g": 128, "b": 0 },
    "darkgreen": { "r": 0, "g": 100, "b": 0 },
    "cyan": { "r": 0, "g": 255, "b": 255 },
    "lightblue": { "r": 173, "g": 216, "b": 230 },
    "blue": { "r": 0, "g": 0, "b": 255 },
    "darkblue": { "r": 0, "g": 0, "b": 139 },
    "white": { "r": 255, "g": 255, "b": 255 },
    "lightgray": { "r": 211, "g": 211, "b": 211 },
    "darkgray": { "r": 169, "g": 169, "b": 169 },
    "gray": { "r": 128, "g": 128, "b": 128 },
    "black": { "r": 0, "g": 0, "b": 0 }
}

class ColoursToRGB:

    def __init__(self):
        pass

    @staticmethod
    def lookup(colour):
        if colour in colours_to_rgb:
            d = colours_to_rgb[colour]
            return [d["r"],d["g"],d["b"]]
        if colour.startswith("#") and len(colour)==7:
            r = int(colour[1:3], 16)
            g = int(colour[3:5], 16)
            b = int(colour[5:7], 16)
            return [r,g,b]
        return None