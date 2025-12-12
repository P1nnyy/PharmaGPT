import unittest
import sys
import os
from unittest.mock import patch, mock_open

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.config_loader import load_product_catalog, load_vendor_rules
from src.normalization import load_and_transform_catalog, VENDOR_RULES, PRODUCT_MAPPING

class TestDynamicConfig(unittest.TestCase):
    
    def test_load_product_catalog_structure(self):
        """Verify load_product_catalog returns a list."""
        catalog = load_product_catalog()
        self.assertIsInstance(catalog, list)
        if len(catalog) > 0:
            self.assertIsInstance(catalog[0], dict)
            self.assertIn("known_name", catalog[0])
            
    def test_catalog_transformation(self):
        """Verify transformation logic."""
        # Mock catalog data
        mock_data = [
            {
                "known_name": "Test Drug A",
                "standard_pack": "10s",
                "synonyms": ["TDA", "Drug A"]
            }
        ]
        
        with patch('src.normalization.load_product_catalog', return_value=mock_data):
            mapping = load_and_transform_catalog()
            
            # Check known name mapping
            self.assertIn("Test Drug A", mapping)
            self.assertEqual(mapping["Test Drug A"], ("Test Drug A", "10s"))
            
            # Check synonym mapping
            self.assertIn("TDA", mapping)
            self.assertEqual(mapping["TDA"], ("Test Drug A", "10s"))
            
    def test_vendor_rules_loaded(self):
        """Verify VENDOR_RULES are loaded and contain emm vee traders."""
        self.assertIsInstance(VENDOR_RULES, dict)
        self.assertIn("vendors", VENDOR_RULES)
        self.assertIn("emm vee traders", VENDOR_RULES["vendors"])
        self.assertEqual(
            VENDOR_RULES["vendors"]["emm vee traders"]["calculation_rules"]["rate_divisor"], 
            12.0
        )

if __name__ == '__main__':
    unittest.main()
