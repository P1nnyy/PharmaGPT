from typing import List, Optional, Union, Literal, Any, Dict
from pydantic import BaseModel, Field, model_validator

class DiscountModel(BaseModel):
    """
    Represents a structured discount at line or global level.
    """
    amount: float = Field(0.0, description="The absolute discount amount.")
    percentage: Optional[float] = Field(None, description="The discount percentage.")
    discount_type: Literal['trade', 'scheme', 'cash', 'other', 'none'] = Field('none', description="Type of discount (trade, scheme, cash).")

class TaxModel(BaseModel):
    """
    Represents a structured tax entry (SGST, CGST, etc).
    """
    tax_type: Literal['SGST', 'CGST', 'IGST', 'GST'] = Field(..., description="The type of tax.")
    percentage: float = Field(..., description="Tax percentage rate.")
    amount: float = Field(..., description="The absolute tax amount.")

class LineItemModel(BaseModel):
    """
    Enterprise-grade Line Item model with mathematical integrity checks (V2).
    """
    product_name: str = Field(..., alias="Product", description="Standardized product name.")
    quantity: float = Field(..., alias="Qty", description="Billed Quantity.")
    unit_price: float = Field(..., alias="Rate", description="Base Unit Rate (Extracted).")
    gross_amount: float = Field(..., alias="Amount", description="The stated row total before discounts/taxes.")
    
    # Nested Structures
    discounts: List[DiscountModel] = Field(default_factory=list)
    taxes: List[TaxModel] = Field(default_factory=list)
    
    # Metadata
    batch: Optional[str] = Field(None, alias="Batch")
    expiry: Optional[str] = Field(None, alias="Expiry")
    mrp: Optional[float] = Field(None, alias="MRP")
    hsn: Optional[str] = Field(None, alias="HSN")

    @model_validator(mode='after')
    def validate_math(self) -> 'LineItemModel':
        """
        Verify that unit_price * quantity accurately reflects the gross_amount.
        Allowing for minor precision differences (0.05).
        """
        expected_gross = round(self.unit_price * self.quantity, 2)
        if abs(expected_gross - self.gross_amount) > 0.05:
            raise ValueError(
                f"Mathematical Mismatch in {self.product_name}: "
                f"{self.unit_price} * {self.quantity} = {expected_gross}, "
                f"but stated Amount is {self.gross_amount}"
            )
        return self

class InvoiceSummaryModel(BaseModel):
    """
    Consolidated footer summary for ledger-perfect indexing.
    """
    sub_total: float = Field(0.0, description="Gross total of all line items.")
    total_discount: float = Field(0.0, description="Sum of all types of discounts.")
    taxable_value: float = Field(0.0, description="Subtotal - Trade Discounts.")
    total_tax: float = Field(0.0, description="Sum of all tax components.")
    round_off: float = Field(0.0, description="Paise-level rounding adjustment.")
    grand_total: float = Field(..., description="Final amount payable (The Truth).")
    
    # Traceability
    discounts_breakdown: List[DiscountModel] = Field(default_factory=list)
    taxes_breakdown: List[TaxModel] = Field(default_factory=list)

class RawLineItem(BaseModel):
    """
    Represents a single line item extracted from an invoice in its raw form.
    BLIND EXTRACTION SCHEMA: Captures only what is seen, no math.
    """
    Product: Union[str, List[str]] = Field(..., description="The product description exactly as it appears on the invoice.")
    Qty: Optional[Union[str, float, List[Any]]] = Field(None, description="Quantity extracted.")
    Free: Optional[Union[str, float, List[Any]]] = Field(None, description="Free/Bonus Quantity.")
    Batch: Optional[Union[str, List[str]]] = Field(None, description="Batch number.")
    Category: Optional[Union[str, List[str]]] = Field(None, description="Extracted Category (Tablet, Syrup, Injection, etc).")
    
    # New Blind Fields
    Amount: Optional[Union[str, float, List[Any]]] = Field(None, description="The neutral column value (Amount/Total) found on the invoice.")
    Rate: Optional[Union[float, str, List[Any]]] = Field(None, description="Unit Price.")
    MRP: Optional[Union[float, str, List[Any]]] = Field(None, description="MRP if available.")
    Expiry: Optional[Union[str, List[str]]] = Field(None, description="Expiry date content.")
    HSN: Optional[Union[str, List[str]]] = Field(None, description="HSN/SAC code.")
    
    # Transport Field (Filled by Solver)
    Net_Line_Amount: Optional[float] = Field(None, description="Calculated Net Amount (Reconciled) from Solver.")
    Calculated_Cost_Price_Per_Unit: Optional[float] = Field(None, description="Calculated Cost Price Per Unit (Reconciled).")
    Logic_Note: Optional[str] = Field(None, description="Explanation of Solver logic.")
    
    # Tax Field
    Raw_GST_Percentage: Optional[float] = Field(None, description="Extracted GST Percentage (Sum of SGST+CGST or IGST).")

    # New Field for Manufacturer Extraction
    Manufacturer: Optional[Union[str, List[str]]] = Field(None, description="The manufacturer or company name extracted from the line item.")
    effective_landing_cost: float = Field(0.0, description="The true cost of the item after tax and global discounts.")

    @model_validator(mode='before')
    @classmethod
    def ensure_strings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
            
        # Text fields that should be joined if they are lists
        text_fields = ['Product', 'Batch', 'Manufacturer', 'HSN', 'Expiry', 'Category']
        for field in text_fields:
            if field in data and isinstance(data[field], list):
                data[field] = " ".join(str(x) for x in data[field])
        
        # Numeric fields that might come as lists (pick first)
        num_fields = ['Qty', 'Free', 'Amount', 'Rate', 'MRP']
        for field in num_fields:
            if field in data and isinstance(data[field], list) and len(data[field]) > 0:
                data[field] = data[field][0]
                
        return data

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

    # Strict Ledger Fields
    sub_total: Union[float, None] = Field(0.0, description="Pre-tax, pre-discount total of all line items.")
    global_discount: Union[float, None] = Field(0.0, description="Global discount applied to the entire invoice.")
    taxable_value: Union[float, None] = Field(0.0, description="Sub-total minus global discount.")
    total_sgst: Union[float, None] = Field(0.0, description="Total SGST from the footer.")
    total_cgst: Union[float, None] = Field(0.0, description="Total CGST from the footer.")
    round_off: Union[float, None] = Field(0.0, description="Rounding adjustment.")
    grand_total: Union[float, None] = Field(0.0, description="Final reconciled total amount.")

class NormalizedLineItem(BaseModel):
    """
    Represents the standardized 'clean invoice' format, corresponding to the (:Line_Item) node.
    """
    Standard_Item_Name: str = Field(..., description="Standardized name of the item.")
    Pack_Size_Description: str = Field(..., description="Description of the pack size.")
    Standard_Quantity: float = Field(..., description="Total units/packs (Billed + Free).")
    Free_Quantity: float = Field(default=0.0, description="Bonus/Free quantity included in Standard_Quantity.")
    
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
    
    # Financials
    Calculated_Tax_Amount: Optional[float] = Field(None, description="Calculated Tax Amount based on Rate.")
    effective_landing_cost: float = Field(0.0, description="The true cost of the item after tax and global discounts.")

    # --- New Ops/Pharma Fields ---
    is_enriched: bool = Field(False, description="True if data was fetched from the internet.")
    salt_composition: Optional[str] = Field(None, description="Detailed salt composition from web.")
    manufacturer: Optional[str] = Field(None, description="Manufacturer from web.")
    
    Salt: Optional[str] = Field(None, description="Composition / Salt (Legacy).")
    Category: Optional[str] = Field(None, description="Item Category (TAB, SYP, INJ, etc).")
    Manufacturer: str = Field("Unknown", description="Standardized manufacturer name (Legacy).")
    
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
    
    # Updated Core Fields
    category: Optional[str] = Field(None, description="Product Category (e.g. Tablet, Syrup).")
    rack_location: Optional[str] = Field(None, description="Physical storage location (e.g. A-12-04).")
    min_stock_alert: Optional[int] = Field(None, description="Minimum stock threshold.")
    
    schedule: Optional[str] = Field(None, description="Drug Schedule (e.g. H, H1).")
    
    # New: Multi-Unit Support
    packaging_variants: List[PackagingVariant] = Field(default_factory=list, description="List of packaging variants.")

class EnrichedProductResponse(BaseModel):
    """
    Response model for product enrichment agent.
    """
    manufacturer: Optional[str] = Field(None, description="Enriched Manufacturer Name")
    salt_composition: Optional[str] = Field(None, description="Enriched Salt Composition")
    pack_size: Optional[str] = Field(None, description="Enriched Pack Size")
    category: Optional[str] = Field(None, description="Enriched Category")
    source_url: Optional[str] = Field(None, description="Source URL of the data")
    error: Optional[str] = Field(None, description="Error message if any")
