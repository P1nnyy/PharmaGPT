from src.domain.normalization.text import structure_packaging_hierarchy

def test_cases():
    cases = [
        ("100ML", {"primary_pack_size": 1, "base_unit": "Bottle"}),
        ("50GM", {"primary_pack_size": 1, "base_unit": "Tube"}),
        ("1L", {"primary_pack_size": 1, "base_unit": "Bottle"}),
        ("15s", {"primary_pack_size": 15, "base_unit": "Tablet"}),
        ("10x10", {"primary_pack_size": 10, "secondary_pack_size": 10, "base_unit": "Tablet"}),
        ("10 TAB", {"primary_pack_size": 10, "base_unit": "Tablet"}),
        ("Unknown", None)
    ]

    print("Running Tests for structure_packaging_hierarchy...")
    for inp, expected in cases:
        result = structure_packaging_hierarchy(inp)
        
        # Simplify result for comparison
        if result:
            simple_res = {k: result[k] for k in ["primary_pack_size", "base_unit", "secondary_pack_size"] if k in result}
        else:
            simple_res = None
            
        status = "PASS" if simple_res == expected else f"FAIL (Got {simple_res})"
        print(f"Input: {inp:<10} | Expected: {str(expected):<40} | {status}")

if __name__ == "__main__":
    test_cases()
