import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("New Store Allocation - Curve Based")

# -----------------------------
# FILE UPLOADS
# -----------------------------

dc_file = st.file_uploader("Upload Display Capacity File", type=["csv"])
style_file = st.file_uploader("Upload Style Master File", type=["csv"])
wh_file = st.file_uploader("Upload WH SOH File", type=["csv"])
curve_file = st.file_uploader("Upload Size Curve File", type=["csv"])
size_master_file = st.file_uploader("Upload Style Size Master File", type=["csv"])

# -----------------------------
# MAIN LOGIC
# -----------------------------

if dc_file and style_file and wh_file and curve_file and size_master_file:

    if st.button("Run Allocation"):

        # Read Files
        dc_df = pd.read_csv(dc_file)
        style_df = pd.read_csv(style_file)
        wh_df = pd.read_csv(wh_file)
        curve_df = pd.read_csv(curve_file)
        size_master_df = pd.read_csv(size_master_file)

        # ---------------------------------------------------
        # STEP 1 : CUTSET CHECK (75% SIZE AVAILABILITY)
        # ---------------------------------------------------

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

        # ---------------------------------------------------
        # STEP 2 : ALLOCATION BASED ON CURVE
        # ---------------------------------------------------

        allocation_list = []

        for store in dc_df["Store"].unique():

            store_dc_data = dc_df[dc_df["Store"] == store]

            for _, dc_row in store_dc_data.iterrows():

                dept = dc_row["Dept"]
                subdept = dc_row["SubDept"]
                clas = dc_row["Class"]
                subclass = dc_row["SubClass"]
                mc = dc_row["MC"]

                dc_value = dc_row["DisplayCapacity"]

                # Get curve for this hierarchy
                hierarchy_curve = curve_df[
                    (curve_df["Dept"] == dept) &
                    (curve_df["SubDept"] == subdept) &
                    (curve_df["Class"] == clas) &
                    (curve_df["SubClass"] == subclass) &
                    (curve_df["MC"] == mc)
                ]

                total_curve = hierarchy_curve["CurveQty"].sum()

                if total_curve == 0:
                    continue

                # Get eligible styles for same hierarchy
                styles_in_hierarchy = eligible_data[
                    (eligible_data["Dept"] == dept) &
                    (eligible_data["SubDept"] == subdept) &
                    (eligible_data["Class"] == clas) &
                    (eligible_data["SubClass"] == subclass) &
                    (eligible_data["MC"] == mc)
                ]["Style"].unique()

                for style in styles_in_hierarchy:

                    # Stop when DC finished
                    if dc_value < total_curve:
                        break

                    style_data = eligible_data[
                        (eligible_data["Style"] == style) &
                        (eligible_data["Dept"] == dept) &
                        (eligible_data["SubDept"] == subdept) &
                        (eligible_data["Class"] == clas) &
                        (eligible_data["SubClass"] == subclass) &
                        (eligible_data["MC"] == mc)
                    ]

                    # Merge size curve
                    style_data = style_data.merge(
                        hierarchy_curve,
                        on=["Dept","SubDept","Class","SubClass","MC","Size"],
                        how="left"
                    )

                    # Allocate ONLY curve qty
                    for _, row in style_data.iterrows():

                        allocation_list.append({
                            "Store": store,
                            "Dept": dept,
                            "SubDept": subdept,
                            "Class": clas,
                            "SubClass": subclass,
                            "MC": mc,
                            "Style": style,
                            "EAN": row["EAN"],
                            "Size": row["Size"],
                            "AllocatedQty": row["CurveQty"]
                        })

                    # Reduce DC after one full curve set
                    dc_value -= total_curve

        # ---------------------------------------------------
        # OUTPUT
        # ---------------------------------------------------

        result = pd.DataFrame(allocation_list)

        st.success("Allocation Completed Successfully")

        st.dataframe(result)

        st.download_button(
            "Download Allocation",
            result.to_csv(index=False),
            file_name="allocation_output.csv",
            mime="text/csv"
        )

else:
    st.info("Please upload all required files.")