
import streamlit as st
import pandas as pd

st.set_page_config(page_title="CPA Automation & Tax Portal", layout="wide")

st.title("🏛️ CPA Automated Back-Office & Tax Portal")
st.markdown("### Client Ingestion, Anomaly Detection & Form Filing Engine")

# Sidebar for Client Selection
st.sidebar.header("Client Management")
client_choice = st.sidebar.selectbox(
    "Select Test Client",
    [
        "Berlin Turnpike Mobil & Mart (Gas Station / 1120-S)",
        "Newington Slice & Grill (Restaurant / 1065)",
        "Rocky Hill Pro Plumbing LLC (Trades / 1120-S)",
        "CT Airport Rideshare (Gig Fleet / Schedule C)",
        "West Hartford Glow Studio (Salon / 1120-S)",
        "Hartford Digital & E-Com (E-Commerce / 1120-S)"
    ]
)

uploaded_file = st.sidebar.file_uploader("Upload Client Bank Statement (PDF or CSV)", type=["pdf", "csv"])

# Main Dashboard Layout
col1, col2, col3, col4 = st.columns(4)

if "Gas Station" in client_choice:
    col1.metric("YTD Gross Revenue", "$446,000.00", "+12% vs last yr")
    col2.metric("Total Operating Expenses", "$106,610.00", "Optimized")
    col3.metric("CT OS-114 Tax Due", "$25,344.00", "Ready to File")
    col4.metric("Audit Risk Flags", "1 Minor", "Cash Shrinkage")
    
    st.subheader("📋 Tax Forms & Schedule Line Mapping")
    form_data = {
        "Tax Form": ["Form 1120-S", "Form 1125-A", "CT Form OS-114", "Town Personal Property"],
        "Filing Period": ["Annual (2026)", "Annual (2026)", "Monthly / Periodic", "Due Nov 1"],
        "Key Line Item": ["Line 1a (Gross Receipts)", "Line 2 (Purchases)", "Line 1 & 3 (Sales/Meals)", "Town Declaration Schedule"],
        "Calculated Amount": ["$446,000.00", "$98,000.00", "$25,344.00", "$65,000.00 Basis"],
        "Status": ["Ready for CPA", "Ready for CPA", "Automated Draft", "Ready for E-File"]
    }
    st.table(pd.DataFrame(form_data))
    
    st.subheader("🚨 Automated Anomaly & Exception Queue")
    st.warning("⚠️ Cash Register Discrepancy Detected: -$35.00 cash shrinkage logged in June and August Z-tapes. Reconciled against net bank deposit.")

elif "Plumbing" in client_choice:
    col1.metric("YTD Gross Revenue", "$185,000.00", "+8%")
    col2.metric("Total Operating Expenses", "$55,000.00", "Optimized")
    col3.metric("Section 179 Deduction", "$14,500.00", "ProPress Added")
    col4.metric("Audit Risk Flags", "2 Critical", "Action Required")
    
    st.subheader("📋 Tax Forms & Schedule Line Mapping")
    form_data = {
        "Tax Form": ["Form 1120-S", "Form 1125-A", "Form 4562", "Form 1099-NEC"],
        "Filing Period": ["Annual (2026)", "Annual (2026)", "Annual (Depreciation)", "Due Jan 31"],
        "Key Line Item": ["Line 1a (Gross Receipts)", "Line 4 (Subcontractors)", "Part I (Section 179)", "Vendor Info Return"],
        "Calculated Amount": ["$185,000.00", "$1,850.00 Sub", "$14,500.00 Asset", "1 Missing W-9 ($1,850)"],
        "Status": ["Ready for CPA", "Flagged Sub", "Calculated", "SMS W-9 Triggered"]
    }
    st.table(pd.DataFrame(form_data))
    
    st.subheader("🚨 Automated Anomaly & Exception Queue")
    st.error("🚨 1099-NEC Compliance Violation: Mike Drywall paid $1,850 via Zelle with NO W-9 on file. SMS text request automatically dispatched to client.")
    st.info("ℹ️ Fixed Asset Reclassification: $14,500 Ridgid ProPress moved from Operating Supplies to Section 179 Fixed Assets for Newington/Rocky Hill Property Tax declaration.")

else:
    col1.metric("YTD Gross Revenue", "$150,000.00", "Stable")
    col2.metric("Total Operating Expenses", "$45,000.00", "Optimized")
    col3.metric("Tax Liability Estimated", "$14,200.00", "Quarterly Safe Harbor")
    col4.metric("Audit Risk Flags", "0", "Clean Books")
    
    st.subheader("📋 Tax Forms & Schedule Line Mapping")
    form_data = {
        "Tax Form": ["Schedule C / 1120-S", "Form 4562", "Schedule M-1", "State Compliance"],
        "Filing Period": ["Annual (2026)", "Annual (2026)", "Annual (2026)", "Periodic"],
        "Key Line Item": ["Line 1 / Gross Receipts", "Depreciation Schedule", "Book-to-Tax Adjustments", "State Returns"],
        "Calculated Amount": ["$150,000.00", "Optimized", "Reconciled", "Up to Date"],
        "Status": ["Ready for CPA", "Ready for CPA", "Ready for CPA", "Compliant"]
    }
    st.table(pd.DataFrame(form_data))

st.sidebar.markdown("---")
st.sidebar.download_button(
    label="📥 Download CPA Workpaper Packet (.xlsx)",
    data=b"dummy_excel_bytes",
    file_name="CPA_Automated_Workpapers_2026.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
