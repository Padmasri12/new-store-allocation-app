import streamlit as st
import pandas as pd

st.title("New Store Allocation - AOP Engine")

dc_file = st.file_uploader("Upload Display Capacity", type=["csv"])
style_file = st.file_uploader("Upload Style Master", type=["csv"])
wh_file = st.file_uploader("Upload WH SOH", type=["csv"])
curve_file = st.file_uploader("Upload Size Curve", type=["csv"])
size_master_file = st.file_uploader("Upload Style Size Master", type=["csv"])

if st.button("Run Allocation"):

    dc_df = pd.read_csv(dc_file)
    style_df = pd.read_csv(style_file)
    wh_df = pd.read_csv(wh_file)
    curve_df = pd.read_csv(curve_file)
    size_master_df = pd.read_csv(size_master_file)

    style_stock = style_df.merge(wh_df, on="EAN", how="left")
    style_stock["WH_Qty"] = style_stock["WH_Qty"].fillna(0)
    style_stock["Size_Available"] = style_stock["WH_Qty"] > 0

    available_sizes = (
        style_stock.groupby("Style")
        .agg(Available_Sizes=("Size_Available", "sum"))
        .reset_index()
    )

    availability = available_sizes.merge(
        size_master_df,
        on="Style",
        how="left"
    )

    availability["Availability_%"] = (
        availability["Available_Sizes"] /
        availability["TotalSizes"]
    )

    eligible_styles = availability[
        availability["Availability_%"] >= 0.75
    ]["Style"]

    eligible_data = style_stock[
        style_stock["Style"].isin(eligible_styles)
    ]

    allocation_list = []

    for store in dc_df["Store"].unique():

        store_dc = dc_df[dc_df["Store"] == store]

        for style in eligible_styles:

            style_data = eligible_data[
                eligible_data["Style"] == style
            ]

            if style_data.empty:
                continue

            mc = style_data["MC"].iloc[0]

            dc_value = store_dc[
                store_dc["MC"] == mc
            ]["DisplayCapacity"].sum()

            style_data = style_data.merge(
                curve_df,
                on=["Dept","SubDept","Class","SubClass","MC","Size"],
                how="left"
            )

            total_curve = style_data["CurveQty"].sum()

            if total_curve == 0:
                continue

            full_sets = int(dc_value / total_curve)

            for _, row in style_data.iterrows():

                alloc_qty = min(
                    full_sets * row["CurveQty"],
                    row["WH_Qty"]
                )

                allocation_list.append({
                    "Store": store,
                    "Style": style,
                    "EAN": row["EAN"],
                    "Size": row["Size"],
                    "AllocatedQty": alloc_qty
                })

    result = pd.DataFrame(allocation_list)

    st.write(result)

    st.download_button(
        "Download Allocation",
        result.to_csv(index=False),
        file_name="allocation_output.csv"
    )