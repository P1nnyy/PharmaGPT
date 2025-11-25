import streamlit as st
import pandas as pd
from datetime import date, timedelta
from shop_manager import PharmaShop
from agent import run_agent
import os

st.set_page_config(page_title="SmartPharma", layout="wide")

# Initialize connection
@st.cache_resource
def get_shop():
    return PharmaShop()

shop = get_shop()

st.title("💊 SmartPharma Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(["💬 AI Agent", "🛒 Cashier (POS)", "📦 Inventory Manager", "📝 Manager Portal"])

with tab1:
    st.header("Talk to your Inventory")
    st.markdown("Ask questions like: *'Do we have Dolo?'* or *'Sell 2 units of Dolo'*")
    
    # Check for API Key
    if not os.getenv("GOOGLE_API_KEY"):
        st.warning("⚠️ GOOGLE_API_KEY not found. The agent might fail. Please add it to .env")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What can I help you with?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = run_agent(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"Agent Error: {e}")

with tab2:
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
                    result = shop.sell_item(selected_product, int(qty))
                    
                    # Result is now a dict: {"status": "success", "tax": float, ...}
                    if result and result.get("status") == "success":
                        st.success(f"✅ Sold {qty} units of {selected_product}!")
                        st.info(f"💰 Tax Collected: ${result['tax']:.2f}")
                        st.caption(f"Details: {result['details']}")
                    else:
                        st.error("❌ Transaction Failed.")
                except ValueError as ve:
                    st.error(f"❌ {ve}")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please select a product.")

with tab3:
    st.header("Inventory Status")
    
    if st.button("Refresh Inventory"):
        st.rerun()
        
    try:
        data = shop.check_inventory()
        
        if data:
            df = pd.DataFrame(data)
            
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

with tab4:
    st.header("📝 Manager Portal")
    st.markdown("### Add New Stock")
    
    with st.form("add_stock_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_product_name = st.text_input("Product Name")
            new_batch_id = st.text_input("Batch ID")
            new_pack_size = st.number_input("Pack Size (Tablets per Strip)", min_value=1, value=10, step=1)
        with col2:
            new_expiry_date = st.date_input("Expiry Date")
            new_quantity = st.number_input("Quantity (Strips/Boxes)", min_value=1, step=1)
            
        submitted = st.form_submit_button("Add to Inventory")
        
        if submitted:
            if new_product_name and new_batch_id:
                try:
                    # Convert date to string YYYY-MM-DD
                    expiry_str = new_expiry_date.strftime("%Y-%m-%d")
                    
                    msg = shop.add_medicine_stock(
                        new_product_name, 
                        new_batch_id, 
                        expiry_str, 
                        int(new_quantity),
                        int(new_pack_size)
                    )
                    st.success(msg)
                except Exception as e:
                    st.error(f"Error adding stock: {e}")
            else:
                st.warning("Please fill in all fields.")
