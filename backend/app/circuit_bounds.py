
import json

with open("./data/bounds.json", "r") as f:
    data = json.load(f)

def normalize(circuit_key, x, y) :

    x_min = data[str(circuit_key)]["x_min"]
    y_max = data[str(circuit_key)]["y_max"]
    scale = data[str(circuit_key)]["scale"]
    x_offset = data[str(circuit_key)]["x_offset"]
    y_offset = data[str(circuit_key)]["y_offset"]
    
    x_norm = ((x - x_min) * scale + x_offset) / 1000
    y_norm = ((y_max - y) * scale + y_offset) / 1000

    return [x_norm, y_norm]