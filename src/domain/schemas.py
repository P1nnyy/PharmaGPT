from typing import List, Optional, Union
from pydantic import BaseModel, Field

class RawLineItem(BaseModel):
    """
    Represents a single line item extracted from an invoice in its raw form.
    BLIND EXTRACTION SCHEMA: Captures only what is seen, no math.
    """
    Product: str = Field(..., description="The product description exactly as it appears on the invoice.")
    Qty: Optional[Union[str, float]] = Field(None, description="Quantity extracted.")
    Free: Optional[Union[str, float]] = Field(None, description="Free/Bonus Quantity.")
    Batch: Optional[str] = Field(None, description="Batch number.")
    
    # New Blind Fields
    Amount: Optional[Union[str, float]] = Field(None, description="The neutral column value (Amount/Total) found on the invoice.")
    Rate: Optional[float] = Field(None, description="Unit Price.")
    MRP: Optional[float] = Field(None, description="MRP if available.")
    Expiry: Optional[str] = Field(None, description="Expiry date content.")
    HSN: Optional[str] = Field(None, description="HSN/SAC code.")
    
    # Transport Field (Filled by Solver)
    Net_Line_Amount: Optional[float] = Field(None, description="Calculated Net Amount (Reconciled) from Solver.")
    Calculated_Cost_Price_Per_Unit: Optional[float] = Field(None, description="Calculated Cost Price Per Unit (Reconciled).")
    Logic_Note: Optional[str] = Field(None, description="Explanation of Solver logic.")

class InvoiceExtraction(BaseModel):
    """
    Represents the full data structure extracted from an invoice document.
    """
    # Header Details - Made Optional for Robustness
    Supplier_Name: Optional[str] = Field("Unknown", description="Name of the supplier (e.g. 'Deepak Agencies').")
    Invoice_No: Optional[str] = Field(None, description="Invoice number.")
    Invoice_Date: Optional[str] = Field(None, description="Date of invoice.")
    Line_Items: List[RawLineItem] = Field(default_factory=list, description="List of line items extracted from the invoice tables.")
    Stated_Grand_Total: Union[str, float, None] = Field(None, description="The Total Amount Payable or Grand Total as stated on the invoice.")
    
    # Global Modifiers (Optional)
    Global_Discount_Amount: Union[str, float, None] = Field(None)
    Freight_Charges: Union[str, float, None] = Field(None)
    SGST_Amount: Union[str, float, None] = Field(None, description="Total SGST Amount from footer.")
    CGST_Amount: Union[str, float, None] = Field(None, description="Total CGST Amount from footer.")
    IGST_Amount: Union[str, float, None] = Field(None, description="Total IGST Amount from footer.")
    Round_Off: Union[str, float, None] = Field(None)
    image_path: Optional[str] = Field(None, description="Relative path to the stored invoice image.")
    raw_text: Optional[str] = Field(None, description="Raw OCR Text for Vector Storage (RAG).")
    trace_id: Optional[str] = Field(None, description="Langfuse Trace ID for debugging.")

class NormalizedLineItem(BaseModel):
    """
    Represents the standardized 'clean invoice' format, corresponding to the (:Line_Item) node.
    """
    Standard_Item_Name: str = Field(..., description="Standardized name of the item.")
    Pack_Size_Description: str = Field(..., description="Description of the pack size.")
    Standard_Quantity: float = Field(..., description="Total units/packs.")
    
    # Net Amount (Passed Through)
    Net_Line_Amount: float = Field(..., description="Total final cost of the line item (Invoice Value).")
    
    # The Critical Value for the Shop
    Final_Unit_Cost: float = Field(..., description="Landed Cost per unit (Net / Qty).")
    Logic_Note: str = Field(..., description="Traceability note from the Solver.")
    
    # Metadata
    HSN_Code: Optional[str] = Field(None, description="HSN Code.")
    MRP: Optional[float] = Field(None, description="MRP.")
    Rate: Optional[float] = Field(None, description="Unit Price (Rate).")
    Expiry_Date: Optional[str] = Field(None, description="Expiry date.")
    Batch_No: Optional[str] = Field(None)

    # --- New Ops/Pharma Fields ---
    Salt: Optional[str] = Field(None, description="Composition / Salt.")
    Category: Optional[str] = Field(None, description="Item Category (TAB, SYP, INJ, etc).")
    Manufacturer: Optional[str] = Field(None, description="Manufacturer Name.")
    
    # Units
    Unit_1st: Optional[str] = Field(None, description="Primary Unit (e.g. TAB).")
    Unit_2nd: Optional[str] = Field(None, description="Secondary Unit (e.g. STRIP/BOX).")
    
    # Pricing (Sales Rates)
    Sales_Rate_A: Optional[float] = Field(None, description="Sales Rate A.")
    Sales_Rate_B: Optional[float] = Field(None, description="Sales Rate B.")
    Sales_Rate_C: Optional[float] = Field(None, description="Sales Rate C.")
    
    # Tax Breakups
    SGST_Percent: Optional[float] = Field(None, description="SGST Percentage.")
    CGST_Percent: Optional[float] = Field(None, description="CGST Percentage.")
    IGST_Percent: Optional[float] = Field(None, description="IGST Percentage.")

class SupplierExtraction(BaseModel):
    """
    Dedicated schema for detailed supplier information.
    """
    Supplier_Name: str = Field(..., description="Name of the seller/supplier.")
    Address: Optional[str] = Field(None, description="Full address of the supplier.")
    GSTIN: Optional[str] = Field(None, description="GST Number (GSTIN).")
    DL_No: Optional[str] = Field(None, description="Drug License Number.")
    Phone_Number: Optional[str] = Field(None, description="Contact phone numbers.")
    Email: Optional[str] = Field(None, description="Email address.")

class User(BaseModel):
    """
    Represents a Google OAuth User.
    """
    google_id: str = Field(..., description="Unique Google User ID.")
    email: str = Field(..., description="User's email address.")
    name: str = Field(..., description="Full name from Google Profile.")
    picture: Optional[str] = Field(None, description="URL to profile picture.")

class PackagingVariant(BaseModel):
    """
    Represents a specific packaging configuration for a Global Product.
    e.g., "Strip of 10", "Box of 100".
    """
    unit_name: str = Field(..., description="Unit type name (e.g., Box, Strip, Bottle).")
    pack_size: str = Field(..., description="Pack size description (e.g., 1x10, 10's).")
    mrp: float = Field(..., description="Maximum Retail Price for this specific pack.")
    conversion_factor: int = Field(1, description="How many base units are in this pack.")

class ProductRequest(BaseModel):
    """
    Schema for creating or updating a Global Product in the inventory.
    """
    name: str = Field(..., description="Name of the product.")
    hsn_code: Optional[str] = Field(None, description="Harmonized System of Nomenclature code.")
    item_code: Optional[str] = Field(None, description="Internal Item Code.")
    sale_price: float = Field(..., description="Selling Price (MRP).")
    purchase_price: float = Field(..., description="Purchase Price (Cost).")
    tax_rate: float = Field(..., description="GST Tax Rate (e.g., 5.0, 12.0).")
    opening_stock: float = Field(..., description="Initial Stock Quantity.")
    min_stock: float = Field(..., description="Minimum Stock Level for alerts.")
    location: Optional[str] = Field(None, description="Physical location (Rack/Shelf).")
    is_verified: Optional[bool] = Field(None, description="Verification status of the product.")
    
    # New Fields for Redesign
    manufacturer: Optional[str] = Field(None, description="Manufacturer Name.")
    salt_composition: Optional[str] = Field(None, description="Drug Composition.")
    category: Optional[str] = Field(None, description="Product Category (e.g. Tablet, Syrup).")
    schedule: Optional[str] = Field(None, description="Drug Schedule (e.g. H, H1).")
    
    # New: Multi-Unit Support
    packaging_variants: List[PackagingVariant] = Field(default_factory=list, description="List of packaging variants.")
