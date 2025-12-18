
import pytest
from src.workflow.nodes.auditor import audit_extraction

def test_auditor_deduplication_single_source_summing():
    """
    Case A: Single Source (1 raw row).
    Two identical items should be SUMMED, not dropped.
    """
    state = {
        "image_path": "dummy.jpg",
        "raw_text_rows": ["some raw text"], # Length 1 = Single Source
        "line_item_fragments": [
            {
                "Product": "Viscojoy Tab",
                "Batch": "B123",
                "Qty": 10.0,
                "Rate": 100.0,
                "Amount": 1000.0,
                "Stated_Net_Amount": 1000.0
            },
            {
                "Product": "Viscojoy Tab",
                "Batch": "B123",
                "Qty": 10.0,
                "Rate": 100.0,
                "Amount": 1000.0,
                "Stated_Net_Amount": 1000.0
            }
        ],
        "global_modifiers": {}
    }

    result = audit_extraction(state)
    items = result["line_items"]

    # EXPECTATION: 1 Item, but Quantity = 20, Amount = 2000
    assert len(items) == 1
    assert items[0]["Qty"] == 20.0
    assert items[0]["Amount"] == 2000.0

def test_auditor_deduplication_multi_source_dropping():
    """
    Case B: Multi Source (2+ raw rows).
    Two identical items should be DROPPED (assumed OCR overlap).
    """
    state = {
        "image_path": "dummy.jpg",
        "raw_text_rows": ["zone 1 text", "zone 2 text"], # Length > 1 = Multi Source
        "line_item_fragments": [
            {
                "Product": "Viscojoy Tab",
                "Batch": "B123",
                "Qty": 10.0,
                "Rate": 100.0,
                "Amount": 1000.0,
                "Stated_Net_Amount": 1000.0
            },
            {
                "Product": "Viscojoy Tab",
                "Batch": "B123",
                "Qty": 10.0,
                "Rate": 100.0,
                "Amount": 1000.0,
                "Stated_Net_Amount": 1000.0
            }
        ],
        "global_modifiers": {}
    }

    result = audit_extraction(state)
    items = result["line_items"]

    # EXPECTATION: 1 Item, Quantity = 10 (Duplicate dropped)
    assert len(items) == 1
    assert items[0]["Qty"] == 10.0
    assert items[0]["Amount"] == 1000.0
