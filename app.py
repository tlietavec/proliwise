import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Trip Expense Splitter", page_icon="🚴", layout="centered")

st.title("🚴 Biking Trip Expense Splitter")
st.caption("Adaptive multi-currency engine with integer rounding rules.")

# =========================================================================
# INITIALIZE SESSION MEMORY
# =========================================================================
if "friends" not in st.session_state:
    st.session_state.friends = ["Alex", "Boris", "Charlie", "Dana"]

if "expenses" not in st.session_state:
    st.session_state.expenses = []

# =========================================================================
# SIDEBAR CONTROLS
# =========================================================================
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Target Currency Selection
    target_currency = st.selectbox("Settlement Currency", ["EUR", "HUF", "USD", "GBP"], index=0).upper()
    
    st.markdown("---")
    st.subheader("Group Roster")
    new_friend = st.text_input("Add Friend Name")
    if st.button("Add to Trip") and new_friend:
        clean_name = new_friend.strip()
        if clean_name and clean_name not in st.session_state.friends:
            st.session_state.friends.append(clean_name)
            st.rerun()
            
    st.write("Active Roster:", ", ".join(st.session_state.friends))

# =========================================================================
# MAIN DASHBOARD: INPUT FORM
# =========================================================================
st.subheader("📝 Log New Expense")
with st.form("expense_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        event = st.text_input("Expense Description", placeholder="e.g., Trail Passes, Dinner")
        amount = st.number_input("Amount Paid", min_value=0.0, step=10.0, format="%.2f")
    with col2:
        payer = st.selectbox("Who Paid?", st.session_state.friends)
        currency = st.selectbox("Original Currency", ["EUR", "HUF", "USD", "GBP"], index=0).upper()
        
    beneficiaries = st.multiselect("Split Among (Beneficiaries)", st.session_state.friends, default=st.session_state.friends)
    submit_button = st.form_submit_button(label="Log Transaction")

if submit_button and amount > 0 and event:
    st.session_state.expenses.append({
        "Event": event,
        "Payer": payer,
        "Amount": amount,
        "Currency": currency,
        "Beneficiaries": beneficiaries
    })
    st.toast(f"Logged: {event}")

# =========================================================================
# LIVE TRANSACTION LEDGER
# =========================================================================
if st.session_state.expenses:
    st.subheader("📊 Current Expense Log")
    df_ledger = pd.DataFrame(st.session_state.expenses)
    df_ledger['Beneficiaries'] = df_ledger['Beneficiaries'].apply(lambda x: ", ".join(x))
    st.dataframe(df_ledger, use_container_width=True)
    
    if st.button("🗑️ Clear All Expenses"):
        st.session_state.expenses = []
        st.rerun()
else:
    st.info("No expenses logged yet. Fill out the form above to start tracking your trip.")

# =========================================================================
# PROCESSING CORE (ADAPTIVE GREEDY / BANKER ALGORITHM)
# =========================================================================
if st.session_state.expenses:
    st.markdown("---")
    st.subheader("🏁 Optimized Settlement Matrix")
    
    with st.spinner("Fetching market exchange rates..."):
        try:
            url = f"https://open.er-api.com/v6/latest/{target_currency}"
            rates = requests.get(url).json().get("rates", {})
        except Exception:
            rates = {target_currency: 1.0}
            st.error("Rate API offline. Defaulting to 1:1 local parity.")

    # Ingest logs and map net balances
    balances = {name: 0.0 for name in st.session_state.friends}
    
    for exp in st.session_state.expenses:
        curr = exp["Currency"]
        conv_rate = rates.get(curr, 1.0)
        normalized_amount = exp["Amount"] / conv_rate
        
        if not exp["Beneficiaries"]:
            continue
        split_share = normalized_amount / len(exp["Beneficiaries"])
        
        balances[exp["Payer"]] += normalized_amount
        for person in exp["Beneficiaries"]:
            balances[person] -= split_share

    # Classify Pool into Debtors and Creditors using dynamic rounding factors
    creditors = []
    debtors = []
    total_people = 0
    
    # 100 for HUF, 1 for everything else
    round_factor = 100 if target_currency == "HUF" else 1
    
    for p, bal in balances.items():
        net = int(round(bal / round_factor) * round_factor)
        if abs(net) >= round_factor:
            total_people += 1
        if net >= round_factor:
            creditors.append({"name": p, "amount": net})
        elif net <= -round_factor:
            debtors.append({"name": p, "amount": abs(net)})

    # Simulated Greedy Approach
    sim_creditors = sorted(creditors, key=lambda x: x["amount"], reverse=True)
    sim_debtors = sorted(debtors, key=lambda x: x["amount"], reverse=True)
    greedy_rows = []
    
    while sim_debtors and sim_creditors:
        d, c = sim_debtors[0], sim_creditors[0]
        trans = int(min(d["amount"], c["amount"]))
        if trans >= round_factor:
            greedy_rows.append({"Sender": d["name"], "Amount": trans, "Receiver": c["name"]})
        d["amount"] -= trans
        c["amount"] -= trans
        if d["amount"] < round_factor: sim_debtors.pop(0)
        if c["amount"] < round_factor: sim_creditors.pop(0)

    # Route Strategy Framework
    final_transfers = []
    strategy_used = ""
    max_allowed = total_people - 1
    
    if len(greedy_rows) <= max_allowed:
        final_transfers = greedy_rows
        strategy_used = "Greedy Optimization Model"
    else:
        strategy_used = "Central Clearinghouse Model"
        sorted_creditors = sorted(creditors, key=lambda x: x["amount"], reverse=True)
        banker_name = sorted_creditors[0]["name"] if sorted_creditors else ""
        
        for d in debtors:
            if d["name"] != banker_name:
                final_transfers.append({"Sender": d["name"], "Amount": d["amount"], "Receiver": banker_name})
        for c in creditors:
            if c["name"] != banker_name:
                final_transfers.append({"Sender": banker_name, "Amount": c["amount"], "Receiver": c["name"]})

    # Render Results Layout
    st.success(f"**Strategy Selected:** {strategy_used}")
    
    if final_transfers:
        res_df = pd.DataFrame(final_transfers)
        # Apply clean zero-decimal notation formatting to matches
        res_df["Amount"] = res_df["Amount"].apply(lambda x: f"{x:,.0f} {target_currency}")
        st.table(res_df)
        
        # EXPORT MECHANISMS
        st.subheader("📥 Export Options")
        csv_exp = pd.DataFrame(st.session_state.expenses).to_csv(index=False)
        csv_res = pd.DataFrame(final_transfers).to_csv(index=False)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.download_button("Download Ledger CSV", data=csv_exp, file_name="trip_expenses.csv", mime="text/csv")
        with col_btn2:
            st.download_button("Download Settlement CSV", data=csv_res, file_name="settlement_plan.csv", mime="text/csv")
    else:
        st.info("Balances match perfectly! No transfers necessary.")
