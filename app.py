import streamlit as st
import pandas as pd
from datetime import date, timedelta
from shop_manager import PharmaShop

st.set_page_config(page_title="SmartPharma", layout="wide")

# Initialize connection
# We use cache_resource to keep the connection object alive across reruns
@st.cache_resource
def get_shop():
    return PharmaShop()

shop = get_shop()

st.title("💊 SmartPharma Dashboard")

tab1, tab2 = st.tabs(["🛒 Cashier (POS)", "📦 Inventory Manager"])

with tab1:
    st.header("Point of Sale")
    
    # Fetch products
    try:
        products = shop.get_product_names()
    except Exception as e:
        st.error(f"Error fetching products: {e}")
        products = []
    
    col1, col2 = st.columns(2)
    with col1:
        selected_product = st.selectbox("Select Product", products)
    with col2:
        qty = st.number_input("Quantity", min_value=1, value=1, step=1)
        
    if st.button("SELL", type="primary"):
        if selected_product:
            with st.spinner("Processing transaction..."):
                try:
                    tax = shop.sell_item(selected_product, int(qty))
                    
                    if tax is not None:
                        st.success(f"✅ Sold {qty} units of {selected_product}!")
                        st.info(f"💰 Tax Collected: ${tax:.2f}")
                    else:
                        st.error("❌ Transaction Failed. Check logs/stock.")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please select a product.")

with tab2:
    st.header("Inventory Status")
    
    if st.button("Refresh Inventory"):
        st.rerun()
        
    try:
        data = shop.check_inventory()
        
        if data:
            df = pd.DataFrame(data)
            
            # Ensure Expiry is comparable
            # It should be datetime.date from shop_manager
            
            today = date.today()
            threshold = today + timedelta(days=30)
            
            def highlight_expiry(row):
                expiry = row['Expiry']
                # Check if expiry is a date object
                if isinstance(expiry, date):
                    if expiry < threshold:
                        return ['background-color: #ff4b4b; color: white'] * len(row)
                return [''] * len(row)

            st.dataframe(df.style.apply(highlight_expiry, axis=1), use_container_width=True)
        else:
            st.info("Inventory is empty.")
    except Exception as e:
        st.error(f"Error fetching inventory: {e}")
