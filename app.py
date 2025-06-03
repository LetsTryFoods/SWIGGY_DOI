import streamlit as st
import pandas as pd
from io import BytesIO
import numpy as np

st.set_page_config(page_title="Inventory Dashboard", layout="wide")

# Centered Heading
st.markdown("<h1 style='text-align: center;'>📊 Inventory vs Sales DOI Dashboard</h1>", unsafe_allow_html=True)


# File Uploads
sales_file = st.file_uploader("Upload Sales CSV", type=["csv"])
inventory_file = st.file_uploader("Upload Inventory CSV", type=["csv"])

if sales_file and inventory_file:
    Sales_df = pd.read_csv(sales_file)
    Inventory_df = pd.read_csv(inventory_file)

    # Inventory Aggregation
    inventory_agg = (
        Inventory_df.groupby(['City', 'SkuDescription', 'SkuCode'])[['OpenPoQuantity', 'WarehouseQtyAvailable']]
        .sum()
        .reset_index()
    )

    # ITEM_CODE to PRODUCT_NAME mapping
    item_to_product_map = inventory_agg.set_index('SkuCode')['SkuDescription'].to_dict()
    Sales_df['PRODUCT_NAME'] = Sales_df['ITEM_CODE'].map(item_to_product_map)

    # Date Conversion
    Sales_df['ORDERED_DATE'] = pd.to_datetime(Sales_df['ORDERED_DATE'])

    # Number of Days Input
    unique_days = Sales_df['ORDERED_DATE'].nunique()
    x = st.number_input(f"Select number of recent days to calculate DOI (Max: {unique_days})", min_value=1, max_value=unique_days, value=7)

    # Filter Last x Days
    recent_dates = Sales_df['ORDERED_DATE'].drop_duplicates().sort_values().tail(x)
    filtered_df = Sales_df[Sales_df['ORDERED_DATE'].isin(recent_dates)]

    # Aggregate Sales
    sales_filtered_grouped_df = (
        filtered_df.groupby(['CITY', 'PRODUCT_NAME', 'ITEM_CODE'])['UNITS_SOLD']
        .sum()
        .reset_index()
    )
    sales_filtered_grouped_df['CITY'] = sales_filtered_grouped_df['CITY'].str.upper()

    # Rename Inventory Columns
    inventory_renamed = inventory_agg.rename(columns={
        'City': 'CITY',
        'SkuCode': 'ITEM_CODE',
        'SkuDescription': 'PRODUCT_NAME',
        'OpenPoQuantity': 'OPEN_PO_QUANTITY',
        'WarehouseQtyAvailable': 'WAREHOUSE_QTY'
    })[['CITY', 'ITEM_CODE', 'PRODUCT_NAME', 'OPEN_PO_QUANTITY', 'WAREHOUSE_QTY']]

    # Merge
    sales_selected = sales_filtered_grouped_df[['CITY', 'ITEM_CODE', 'PRODUCT_NAME', 'UNITS_SOLD']]
    merged_df = pd.merge(
        inventory_renamed,
        sales_selected,
        on=['CITY', 'ITEM_CODE', 'PRODUCT_NAME'],
        how='left'
    )

    # Fill NaNs
    merged_df['UNITS_SOLD'] = merged_df['UNITS_SOLD'].fillna(0).astype(int)
    merged_df['WAREHOUSE_QTY'] = merged_df['WAREHOUSE_QTY'].fillna(0).astype(int)
    merged_df['OPEN_PO_QUANTITY'] = merged_df['OPEN_PO_QUANTITY'].fillna(0).astype(int)

    # DOI Calculation
    merged_df['DAILY_SALES'] = merged_df['UNITS_SOLD'] / x
    merged_df['DOI'] = merged_df.apply(
        lambda row: round(row['WAREHOUSE_QTY'] / row['DAILY_SALES'], 2) if row['DAILY_SALES'] > 0 else 0,
        axis=1
    )

    # Remove products with 'gift' or 'celebration' in the product name (case-insensitive)
    merged_df = merged_df[~merged_df['PRODUCT_NAME'].str.contains(r'gift|celebration|sample', case=False, na=False)]


    # Final DF
    final_df = merged_df[['CITY', 'ITEM_CODE', 'PRODUCT_NAME', 'UNITS_SOLD', 'WAREHOUSE_QTY', 'OPEN_PO_QUANTITY', 'DOI']]
    final_df['DOI'] = np.floor(final_df['DOI'])
    final_df = final_df.sort_values(by=['CITY', 'DOI'], ascending=[True, False])


    st.markdown("<h3 style='text-align: center;'>📋 Final Merged and Processed Data</h3>", unsafe_allow_html=True)
    st.dataframe(final_df, use_container_width=True)

    # Excel Download Function
    def convert_df_to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Final Data')
        return output.getvalue()

    excel_file = convert_df_to_excel(final_df)

    # Centered download button using Streamlit columns
    centered_col = st.columns([1, 1, 1])  # [left, center, right]
    with centered_col[1]:
        st.download_button(
            label="📥 Download Final Data as Excel",
            data=excel_file,
            file_name="SWIGGY_DOI.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True  # Optional: makes it stretch inside its column
        )


    # --- Custom DOI Section ---
    st.markdown("---")
    st.markdown("<h3 style='text-align: center;'>🛠️ Create Custom DOI View</h3>", unsafe_allow_html=True)

    # All possible options
    all_cities = sorted(final_df['CITY'].unique().tolist())
    all_products = sorted(final_df['PRODUCT_NAME'].unique().tolist())

    ## Step 1: Initial selections
    selected_cities_raw = st.session_state.get("selected_cities_raw", [])
    selected_products_raw = st.session_state.get("selected_products_raw", [])

    # Step 2: For dropdown options:
    # Cities dropdown options depend on selected products (NOT cities)
    if selected_products_raw and "All" not in selected_products_raw:
        available_cities = sorted(final_df[final_df["PRODUCT_NAME"].isin(selected_products_raw)]["CITY"].unique())
    else:
        available_cities = sorted(final_df["CITY"].unique())

    # Products dropdown options depend on selected cities (NOT products)
    if selected_cities_raw and "All" not in selected_cities_raw:
        available_products = sorted(final_df[final_df["CITY"].isin(selected_cities_raw)]["PRODUCT_NAME"].unique())
    else:
        available_products = sorted(final_df["PRODUCT_NAME"].unique())


    # Step 3: Create dropdowns with "Select All" included
    col1, col2 = st.columns(2)

    with col1:
        selected_cities_raw = st.multiselect(
            "Select City/Cities", 
            options=["All"] + available_cities,
            default=selected_cities_raw,
            key="selected_cities_raw"
        )

    with col2:
        selected_products_raw = st.multiselect(
            "Select Product(s)", 
            options=["All"] + available_products,
            default=selected_products_raw,
            key="selected_products_raw"
        )

    # Step 4: Handle 'All' logic
    selected_cities = all_cities if "All" in selected_cities_raw or not selected_cities_raw else selected_cities_raw
    selected_products = all_products if "All" in selected_products_raw or not selected_products_raw else selected_products_raw

    # Step 5: Final data filter
    filtered_df = final_df[
        final_df['CITY'].isin(selected_cities) & final_df['PRODUCT_NAME'].isin(selected_products)
    ].copy()

    # Step 6: Show info or results
    if not selected_cities_raw and not selected_products_raw:
        st.info("⬆️ Use the city/product filters above to generate a custom DOI table.")
    else:
        # Recalculate metrics
        filtered_df['DAILY_SALES'] = filtered_df['UNITS_SOLD'] / x
        filtered_df['DOI'] = filtered_df.apply(
            lambda row: round(row['WAREHOUSE_QTY'] / row['DAILY_SALES'], 2) if row['DAILY_SALES'] > 0 else 0,
            axis=1
        )

        # CASE 1: Only cities selected (and not products)
        if selected_cities_raw and not selected_products_raw:
            grouped = filtered_df.groupby('CITY')[['UNITS_SOLD', 'WAREHOUSE_QTY', 'OPEN_PO_QUANTITY']].sum().reset_index()
            grouped['DAILY_SALES'] = grouped['UNITS_SOLD'] / x
            grouped['DOI'] = grouped.apply(
                lambda row: round(row['WAREHOUSE_QTY'] / row['DAILY_SALES'], 2) if row['DAILY_SALES'] > 0 else 0,
                axis=1
            )
            grouped['DOI'] = np.floor(grouped['DOI'])
            st.dataframe(grouped, use_container_width=True)

        # CASE 2: Only products selected (and not cities)
        elif selected_products_raw and not selected_cities_raw:
            grouped = filtered_df.groupby('PRODUCT_NAME')[['UNITS_SOLD', 'WAREHOUSE_QTY', 'OPEN_PO_QUANTITY']].sum().reset_index()
            grouped['DAILY_SALES'] = grouped['UNITS_SOLD'] / x
            grouped['DOI'] = grouped.apply(
                lambda row: round(row['WAREHOUSE_QTY'] / row['DAILY_SALES'], 2) if row['DAILY_SALES'] > 0 else 0,
                axis=1
            )
            grouped['DOI'] = np.floor(grouped['DOI'])
            st.dataframe(grouped, use_container_width=True)

        # CASE 3: Show detailed table
        else:
            grouped = filtered_df[['CITY', 'ITEM_CODE', 'PRODUCT_NAME', 'UNITS_SOLD', 'WAREHOUSE_QTY', 'OPEN_PO_QUANTITY', 'DOI']]
            grouped['DOI'] = np.floor(grouped['DOI'])
            st.dataframe(grouped, use_container_width=True)





