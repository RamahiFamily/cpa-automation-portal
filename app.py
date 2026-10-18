import streamlit as st
import pandas as pd

# 1. Page Configuration & Professional Styling
st.set_page_config(
    page_title="CPA Back-Office & Tax Portal",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# 2. Sidebar Navigation
st.sidebar.title("🏛️ CPA Automations")
st.sidebar.markdown("---")

app_mode = st.sidebar.radio("Navigation Mode", ["🔍 Client Deep-Dive Portal", "📊 CPA Firm Master Dashboard"])

# 3. Mode 1: Client Deep-Dive Portal
if app_mode == "🔍 Client Deep-Dive Portal":
    st.sidebar.markdown("### Client Selection")
    client_choice = st.sidebar.selectbox(
        "Active Client Profile",
        [
            "Berlin Turnpike Mobil & Mart (Gas Station / 1120-S)",
            "Newington Slice & Grill (Restaurant / 1065)",
            "Rocky Hill Pro Plumbing LLC (Trades / 1120-S)",
            "CT Airport Rideshare (Gig Fleet / Schedule C)",
            "West Hartford Glow Studio (Salon / 1120-S)",
            "Hartford Digital & E-Com (E-Commerce / 1120-S)"
        ]
    )
    
    st.sidebar.markdown("---")
    uploaded_file = st.sidebar.file_uploader("Upload New Bank Statement / POS (PDF/CSV)", type=["pdf", "csv"])
    if uploaded_file:
        st.sidebar.success(f"✅ Loaded: {uploaded_file.name}")

    st.title(f"📁 Client Portal: {client_choice.split('(')[0]}")
    st.markdown("Automated General Ledger Reconcile, Tax Line Mapping & Compliance Engine.")
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    if "Gas Station" in client_choice:
        col1.metric("YTD Gross Revenue", "$446,000.00", "+12% YoY")
        col2.metric("Operating Expenses", "$106,610.00", "Optimized")
        col3.metric("CT OS-114 Tax Due", "$25,344.00", "Due Monthly")
        col4.metric("Audit Risk Level", "Low", "1 Cash Variance")
    elif "Plumbing" in client_choice:
        col1.metric("YTD Gross Revenue", "$185,000.00", "+8% YoY")
        col2.metric("Operating Expenses", "$55,000.00", "Optimized")
        col3.metric("Section 179 Cap", "$14,500.00", "ProPress Added")
        col4.metric("Audit Risk Level", "High", "Missing W-9")
    else:
        col1.metric("YTD Gross Revenue", "$150,000.00", "Stable")
        col2.metric("Operating Expenses", "$45,000.00", "Optimized")
        col3.metric("Est. Tax Liability", "$14,200.00", "Quarterly Safe Harbor")
        col4.metric("Audit Risk Level", "Clean", "No Exceptions")

    st.markdown("### ")

    tab1, tab2, tab3 = st.tabs(["📋 IRS & State Tax Form Mapping", "🚨 Automated Exception Queue", "📥 Workpaper & File Export"])

    with tab1:
        st.subheader("Tax Return Line Item Reconciliation")
        if "Gas Station" in client_choice:
            df_form = pd.DataFrame({
                "Tax Form / Schedule": ["Form 1120-S", "Form 1125-A", "CT Form OS-114", "Town Personal Property"],
                "Filing Frequency": ["Annual", "Annual", "Monthly", "Annual (Nov 1)"],
                "Key Line Mapping": ["Line 1a (Gross Receipts)", "Line 2 (Purchases)", "Line 1 & Line 3 (Sales/Meals)", "Town Equipment Declaration"],
                "Calculated Amount": ["$446,000.00", "$98,000.00", "$25,344.00 Tax", "$65,000.00 Basis"],
                "Status": ["Ready for CPA", "Ready for CPA", "Draft Generated", "Ready to E-File"]
            })
        else:
            df_form = pd.DataFrame({
                "Tax Form / Schedule": ["Form 1120-S / Sch C", "Form 4562", "Schedule M-1", "State Tax Compliance"],
                "Filing Frequency": ["Annual", "Annual", "Annual", "Periodic"],
                "Key Line Mapping": ["Line 1 / Gross Receipts", "Part I (Depreciation)", "Book-to-Tax Adjustments", "State Returns"],
                "Calculated Amount": ["$185,000.00", "Optimized", "Reconciled", "Up-to-Date"],
                "Status": ["Ready for CPA", "Ready for CPA", "Ready for CPA", "Compliant"]
            })
        st.dataframe(df_form, use_container_width=True)

    with tab2:
        st.subheader("AI Audit & Compliance Exception Log")
        if "Plumbing" in client_choice:
            st.error("🚨 **1099-NEC Violation Flag:** Subcontractor 'Mike Drywall' was paid $1,850 via Zelle with **no W-9 on file**. Automated text prompt sent to client.")
            st.warning("⚠️ **Fixed Asset Reclassification:** $14,500 Ridgid ProPress was moved from operating supplies to Section 179 depreciation schedule.")
        elif "Gas Station" in client_choice:
            st.warning("⚠️ **Cash Shrinkage Notice:** -$35.00 cash register shortage detected in June and August Z-tapes; successfully offset against net bank deposit reconciliation.")
        else:
            st.success("✅ No critical audit flags detected. Transaction categorizations are 100% reconciled.")

    with tab3:
        st.subheader("CPA Workpaper Export Center")
        st.write("Download the complete multi-tab Excel workbook containing Trial Balances, M-1 adjustments, and audit reports.")
        st.download_button(
            label="📥 Download CPA Workpaper Packet (.xlsx)",
            data=b"dummy_excel_bytes",
            file_name="CPA_Automated_Workpapers_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# 4. Mode 2: CPA Firm Master Dashboard
else:
    st.title("📊 CPA Firm Master Practice Dashboard")
    st.markdown("Overview of all wholesale client accounts managed by your back-office automation engine.")
    st.markdown("---")

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    fcol1.metric("Active Wholesale Clients", "42 / 100 Target", "+5 this month")
    fcol2.metric("Monthly Recurring Revenue", "$5,250.00 / mo", "96% Margin")
    fcol3.metric("Upcoming Deadlines (Oct/Nov)", "8 Declarations", "Due Nov 1")
    fcol4.metric("Pending Audit Flags", "3 Items", "Requires CPA Review")

    st.markdown("### ")
    st.subheader("📋 Firm Client Portfolio Status")

    master_portfolio = pd.DataFrame({
        "Client Business Name": [
            "Berlin Turnpike Mobil & Mart", "Newington Slice & Grill", 
            "Rocky Hill Pro Plumbing LLC", "CT Airport Rideshare Fleet", 
            "West Hartford Glow Studio", "Hartford Digital & E-Com"
        ],
        "Entity Type": ["1120-S", "1065", "1120-S", "Schedule C", "1120-S", "1120-S"],
        "Last Reconciled": ["Yesterday", "2 days ago", "Today", "3 days ago", "Yesterday", "Today"],
        "Pending Filing": ["CT OS-114", "Form 1065 / OS-114", "Form 1120-S / 1099", "Schedule C", "Form 1120-S", "Form 1120-S"],
        "System Status": ["🟢 Ready to File", "🟡 Missing Info", "🔴 Audit Flag", "🟢 Mileage Optimized", "🟢 Ready to File", "🟢 Ready to File"]
    })

    st.dataframe(master_portfolio, use_container_width=True)
    st.info("💡 **CPA Pitch Note:** Clicking any client row drills down into their specific bank reconciliation queue, reducing staff write-up time from hours to seconds.")
