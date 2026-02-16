
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from domain.normalization.financials import parse_quantity, parse_float

print("Testing parse_quantity('2.75+.250')")
try:
    qty = parse_quantity("2.75+.250")
    print(f"Result: {qty}")
except Exception as e:
    print(f"Error: {e}")

print("Testing parse_quantity('10+2')")
print(f"Result: {parse_quantity('10+2')}")
