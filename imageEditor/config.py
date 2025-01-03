# config.py

import os
import json

def load_config(config_path='config.json'):
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file '{config_path}' not found.")
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config
