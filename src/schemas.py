from typing import List, Optional, Union
from pydantic import BaseModel, Field

class RawLineItem(BaseModel):
    """
    Represents a single line item extracted from an invoice in its raw form.
    Captures diverse column variations found in different invoice formats.
    """
    Original_Product_Description: str = Field(..., description="The product description exactly as it appears on the invoice.")
    Raw_Quantity: Union[str, float] = Field(..., description="Quantity extracted, kept flexible to handle formats like '10 strips' or numeric values.")
    Batch_No: str = Field(..., description="Batch number of the product.")
    Raw_Rate_Column_1: Union[str, float, None] = Field(None, description="Primary rate column (e.g., Rate, Rate/Doz, PTR).")
    Raw_Rate_Column_2: Union[str, float, None] = Field(None, description="Secondary rate column (e.g., MRP) if present.")
    Raw_Discount_Percentage: Union[str, float, None] = Field(None, description="Discount percentage applied to the item.")
    Stated_Net_Amount: Union[str, float] = Field(..., description="The final amount for this line item as stated on the invoice.")

class InvoiceExtraction(BaseModel):
    """
    Represents the full data structure extracted from an invoice document.
    """
    Supplier_Name: str = Field(..., description="Name of the supplier or vendor.")
    Invoice_No: str = Field(..., description="Unique identifier for the invoice.")
    Invoice_Date: str = Field(..., description="Date of the invoice.")
    Line_Items: List[RawLineItem] = Field(default_factory=list, description="List of line items extracted from the invoice tables.")
