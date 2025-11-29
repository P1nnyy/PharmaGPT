import streamlit as st
import pandas as pd
from datetime import date, timedelta
from shop_manager import PharmaShop
from agent import run_agent
from vision_agent import analyze_bill_image
import os

# --- 1. Page Config & CSS Injection ---
st.set_page_config(page_title="PharmaGPT Glass", layout="wide", initial_sidebar_state="collapsed")

def load_css():
    with open("glass_styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# --- 2. Initialize Backend ---
@st.cache_resource
def get_shop():
    return PharmaShop()

shop = get_shop()

# --- 3. Session State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_ingestion" not in st.session_state:
    st.session_state.show_ingestion = False

# --- 4. Layout: "Apple Glass" Interface ---

# --- 4. Layout: "Apple Glass" Interface ---

# A. Header / Title (Minimalist & Animated)
col_h1, col_h2 = st.columns([0.85, 0.15])
with col_h1:
    st.markdown("""
    <div style="animation: fadeInUp 0.5s ease-out;">
        <h1 style="margin:0; font-size: 2.5rem;">💊 PharmaGPT</h1>
        <p style="margin:0; opacity:0.7;">AI-Powered Inventory Intelligence</p>
    </div>
    """, unsafe_allow_html=True)
with col_h2:
    st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True) # Spacer
    if st.button("📸 Scan Bill", type="primary", use_container_width=True):
        st.session_state.show_ingestion = not st.session_state.show_ingestion
        st.rerun()

# B. Ingestion Overlay (Conditional with Animation)
if st.session_state.show_ingestion:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container():
        st.markdown("""
        <div class="glass-card">
            <h3 style="display:flex; align-items:center; gap:10px;">
                🧾 Bill Ingestion <span style="font-size:0.8em; opacity:0.5; font-weight:400;">(Vision Agent)</span>
            </h3>
            <p style="margin-bottom: 20px;">Upload an invoice to automatically extract and normalize inventory data.</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_u1, col_u2 = st.columns([0.85, 0.15])
        with col_u1:
            uploaded_file = st.file_uploader("Drop Invoice (PDF/Image)", type=['png', 'jpg', 'jpeg'], label_visibility="collapsed")
        with col_u2:
            demo_mode = st.button("⚡ Demo", help="Use dummy data")

        if uploaded_file or demo_mode:
            st.info("🤖 Vision Agent Analyzing...")
            
            try:
                if demo_mode:
                    import time
                    time.sleep(1) # Fake processing
                    extracted_data = [
                        {"product_name": "Augmentin 625", "batch_number": "A625-001", "expiry_date": "2025-12-31", "quantity_packs": 10, "pack_size": 6, "mrp": 200.0, "manufacturer": "GSK", "dosage_form": "Tablet"},
                        {"product_name": "Dolo 650", "batch_number": "D650-X99", "expiry_date": "2024-10-15", "quantity_packs": 50, "pack_size": 15, "mrp": 30.0, "manufacturer": "Micro Labs", "dosage_form": "Tablet"},
                        {"product_name": "Pan 40", "batch_number": "P40-221", "expiry_date": "2026-05-20", "quantity_packs": 20, "pack_size": 10, "mrp": 150.0, "manufacturer": "Alkem", "dosage_form": "Tablet"}
                    ]
                else:
                    image_bytes = uploaded_file.getvalue()
                    extracted_data = analyze_bill_image(image_bytes)
                
                if not extracted_data:
                    st.warning("Could not extract data. Please try another image.")
                    extracted_data = []
                
                # Human-Centric Data: Rename columns for display
                df_display = pd.DataFrame(extracted_data)
                column_map = {
                    "product_name": "Product Name",
                    "batch_number": "Batch #",
                    "expiry_date": "Expiry",
                    "quantity_packs": "Qty (Packs)",
                    "pack_size": "Pack Size",
                    "mrp": "MRP",
                    "manufacturer": "Manufacturer",
                    "dosage_form": "Form"
                }
                df_display = df_display.rename(columns=column_map)

                # FIX: Convert Expiry to datetime for st.column_config.DateColumn
                if "Expiry" in df_display.columns:
                    df_display["Expiry"] = pd.to_datetime(df_display["Expiry"], errors='coerce')
                
                st.markdown("#### 🔍 Verify Extracted Data")
                st.caption("Review the AI's extraction. Edit any cells that look incorrect before committing.")
                
                edited_df = st.data_editor(
                    df_display, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    column_config={
                        "Expiry": st.column_config.DateColumn("Expiry", format="YYYY-MM-DD"),
                        "MRP": st.column_config.NumberColumn("MRP", format="$%.2f"),
                        "Qty (Packs)": st.column_config.NumberColumn("Qty", min_value=1),
                    }
                )
                
                col_c1, col_c2 = st.columns([0.2, 0.8])
                with col_c1:
                    if st.button("✅ Commit to Inventory", use_container_width=True):
                        success_count = 0
                        # Reverse map columns to backend keys
                        reverse_map = {v: k for k, v in column_map.items()}
                        
                        for index, row in edited_df.iterrows():
                            try:
                                # Map back to standardized keys
                                data_row = {reverse_map[k]: v for k, v in row.items() if k in reverse_map}
                                
                                shop.add_medicine_stock(
                                    product_name=data_row['product_name'],
                                    batch_id=data_row['batch_number'],
                                    expiry_date=data_row['expiry_date'],
                                    qty_packs=int(data_row['quantity_packs']),
                                    pack_size=int(data_row['pack_size']),
                                    mrp=float(data_row['mrp']),
                                    manufacturer_name=data_row.get('manufacturer', 'Unknown'),
                                    dosage_form=data_row.get('dosage_form', 'Tablet')
                                )
                                success_count += 1
                            except Exception as e:
                                st.error(f"Failed to add {row.get('Product Name')}: {e}")
                        
                        if success_count > 0:
                            st.toast(f"Successfully added {success_count} items!", icon="🎉")
                            st.session_state.show_ingestion = False
                            st.rerun()

            except Exception as e:
                st.error(f"Vision Agent Error: {e}")

# C. Main Spotlight Search (The Agent)
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; margin-bottom: 30px; animation: fadeInUp 0.8s ease-out;">
    <h2 style="font-size: 2rem; margin-bottom: 10px;">What are we looking for?</h2>
    <p style="opacity: 0.6;">Search inventory, ask medical questions, or find stock...</p>
</div>
""", unsafe_allow_html=True)

prompt = st.chat_input("Type your query here...")

# D. Agent Interaction Area
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Agent is thinking..."):
        try:
            response = run_agent(prompt)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(f"Agent Error: {e}")

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# E. Quick Stats / "Head-Up Display"
st.markdown("<br><br>", unsafe_allow_html=True)
with st.expander("📊 Live Inventory Overview (Click to Expand)", expanded=True):
    try:
        data = shop.check_inventory()
        if data:
            df = pd.DataFrame(data)
            
            if not df.empty:
                # Group by Product for the "Container" UI
                products = df['product_name'].unique()
                
                st.markdown(f"**Found {len(products)} Unique Products**")
                
                for product in products:
                    product_df = df[df['product_name'] == product]
                    
                    # Aggregates
                    total_sealed = product_df['quantity_packs'].sum()
                    total_loose = product_df['quantity_loose'].sum()
                    pack_size = product_df['pack_size'].iloc[0]
                    manufacturer = product_df['manufacturer'].iloc[0]
                    form = product_df['dosage_form'].iloc[0]
                    
                    # Visual Header
                    header = f"💊 **{product}** ({form})  |  🏭 {manufacturer}  |  📦 **Total: {total_sealed} Packs** + {total_loose} Loose"
                    
                    with st.expander(header):
                        # Child Rows: Batches
                        display_cols = {
                            "batch_number": "Batch #",
                            "expiry_date": "Expiry",
                            "stock_display": "Stock Status",
                            "mrp": "MRP"
                        }
                        
                        batch_view = product_df.rename(columns=display_cols)
                        cols_to_show = list(display_cols.values())
                        
                        st.dataframe(
                            batch_view[cols_to_show],
                            use_container_width=True,
                            column_config={
                                "Expiry": st.column_config.DateColumn("Expiry", format="YYYY-MM-DD"),
                                "MRP": st.column_config.NumberColumn("MRP", format="$%.2f"),
                            },
                            hide_index=True
                        )
            else:
                st.info("Inventory Empty")
        else:
            st.info("Inventory Empty")

    except Exception as e:
        st.error(f"Connection Error: {e}")

