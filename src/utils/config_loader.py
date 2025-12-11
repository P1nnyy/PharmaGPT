import yaml
import os
from typing import Dict, Any, List

def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    Safely loads a YAML configuration file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file {file_path}: {e}")

def load_vendor_rules(config_dir: str = "config") -> Dict[str, Any]:
    """
    Loads vendor_rules.yaml from the config directory.
    """
    path = os.path.join(os.getcwd(), config_dir, "vendor_rules.yaml")
    return load_yaml_config(path)

def load_product_catalog(config_dir: str = "config") -> List[Dict[str, Any]]:
    """
    Loads product_catalog.yaml from the config directory.
    Returns the list of products.
    """
    path = os.path.join(os.getcwd(), config_dir, "product_catalog.yaml")
    data = load_yaml_config(path)
    return data.get("products", [])
