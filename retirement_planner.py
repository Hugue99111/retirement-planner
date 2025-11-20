import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Retirement Cashflow Optimizer", layout="wide")

st.title("🇬🇧 UK Retirement Withdrawal Dashboard")
st.markdown("""
This tool models the sustainability of your portfolio and calculates a tax-efficient withdrawal schedule.
Adjust the sidebar inputs to reflect your current balances and economic assumptions.
""")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Portfolio Status")
cash_balance = st.sidebar.number_input("Cash Balance (£)", value=307000, step=5000)
isa_balance = st.sidebar.number_input("ISA Balance (£)", value=800000, step=10000)
sipp_balance = st.sidebar.number_input("SIPP Balance (£)", value=800000, step=10000)

st.sidebar.header("2. Assumptions")
inflation_rate = st.sidebar.slider("Inflation Rate (%)", 0.0, 10.0, 3.0) / 100
isa_sipp_yield = st.sidebar.slider("Inv. Yield (ISA/SIPP) (%)", 0.0, 10.0, 4.87) / 100
cash_yield = st.sidebar.slider("Cash Yield (%)", 0.0, 10.0, 3.0) / 100

st.sidebar.header("3. Demographics")
age_husband = st.sidebar.number_input("Husband Age", value=64)
age_wife = st.sidebar.number_input("Wife Age", value=56)
planning_horizon = 95 - age_wife  # Planning until wife is 95

st.sidebar.header("4. Spending Needs")
initial_withdrawal = st.sidebar.number_input("Target Annual Withdrawal (Gross)", value=90100, step=1000)
spending_drop_age = 80 # Husband's expected mortality
spending_drop_percent = 0.70

# --- TAX CONSTANTS (2025/26 Estimates) ---
PERSONAL_ALLOWANCE = 12570
BASIC_RATE_LIMIT = 50270
TAX_FREE_SIPP_PCT = 0.25

# --- CALCULATION ENGINE ---
data = []
current_cash = cash_balance
current_isa = isa_balance
current_sipp = sipp_balance
current_withdrawal = initial_withdrawal

h_state_pension_age = 67
w_state_pension_age = 67 # Adjusted to 67 based on birth year ~1969
h_sp_amount = 11502 # Full New State Pension approx
w_sp_amount = 9202  # 80% Full New State Pension

for year in range(planning_horizon + 1):
    h_age = age_husband + year
    w_age = age_wife + year
    
    # 1. Determine Spending Requirement (Inflation Adjusted)
    if h_age >= spending_drop_age and h_age == spending_drop_age:
        # One time drop adjustment
        current_withdrawal = current_withdrawal * spending_drop_percent
    
    req_income = current_withdrawal
    
    # 2. Determine State Pension Income
    sp_income = 0
    if h_age >= h_state_pension_age:
        sp_income += h_sp_amount * ((1 + inflation_rate) ** year)
    if w_age >= w_state_pension_age:
        sp_income += w_sp_amount * ((1 + inflation_rate) ** year)
        
    # 3. Net Portfolio Withdrawal Needed
    portfolio_withdrawal_needed = max(0, req_income - sp_income)
    
    # 4. Asset Growth (Start of Year)
    cash_interest = current_cash * cash_yield
    current_cash += cash_interest
    current_isa *= (1 + isa_sipp_yield)
    current_sipp *= (1 + isa_sipp_yield)
    
    # 5. Withdrawal Logic (Tax Optimization Strategy)
    # Order: Cash Interest > SIPP (up to PA) > ISA > SIPP (Basic Rate) > Cash Principal
    
    remaining_needed = portfolio_withdrawal_needed
    
    # A. Use Cash Interest (Taxable likely, but use it first)
    take_cash = min(current_cash, remaining_needed) # Simplified: taking all cash if needed, prioritising interest
    # Ideally we leave principal, but for simple depletion we take from cash pool
    # Refined Logic:
    # Try to preserve ISA/SIPP tax wrapper. Burn Cash first? 
    # User Logic: Previous model assumed efficient wrapper usage. 
    # Strategy: Tax Efficient Blend.
    
    # Step A: Take SIPP up to Personal Allowance (Effective Tax Free via PCLS + PA)
    # Max tax efficient SIPP w/d per person = PA / 0.75 = £16,760 (approx)
    # Combined efficient SIPP = ~£33,520
    
    sipp_withdrawal = 0
    isa_withdrawal = 0
    cash_withdrawal = 0
    
    # Optimal SIPP Calculation
    # We want taxable income to fill Personal Allowance first
    # Taxable Income = 75% of SIPP Withdrawal.
    # Target Taxable Income = £12,570 * 2 = £25,140
    # Required SIPP Withdrawal to hit this = £25,140 / 0.75 = £33,520
    
    optimal_sipp_wd = 33520 
    
    # Take from SIPP
    take_sipp = min(current_sipp, min(remaining_needed, optimal_sipp_wd))
    sipp_withdrawal += take_sipp
    current_sipp -= take_sipp
    remaining_needed -= take_sipp
    
    # Step B: If we still need money, take from ISA (Tax Free) to avoid tax
    # (Unless ISA is empty, then go back to SIPP or Cash)
    
    if remaining_needed > 0:
        take_isa = min(current_isa, remaining_needed)
        isa_withdrawal += take_isa
        current_isa -= take_isa
        remaining_needed -= take_isa
        
    # Step C: If ISA empty, Cash
    if remaining_needed > 0:
        take_cash = min(current_cash, remaining_needed)
        cash_withdrawal += take_cash
        current_cash -= take_cash
        remaining_needed -= take_cash
        
    # Step D: If Cash empty, back to SIPP (Taxable at Basic Rate)
    if remaining_needed > 0:
        take_sipp_excess = min(current_sipp, remaining_needed)
        sipp_withdrawal += take_sipp_excess
        current_sipp -= take_sipp_excess
        remaining_needed -= take_sipp_excess
        
    total_portfolio = current_cash + current_isa + current_sipp
    
    # Tax Calculation (Estimate)
    # SIPP Taxable = SIPP_WD * 0.75
    taxable_income = sipp_withdrawal * 0.75
    # Allowances (2 people)
    tax_bill = 0
    excess_income = max(0, taxable_income - (PERSONAL_ALLOWANCE * 2))
    tax_bill = excess_income * 0.20 # Assume basic rate for simplicity
    
    net_pocket = (sipp_withdrawal + isa_withdrawal + cash_withdrawal + sp_income) - tax_bill
    
    data.append({
        "Year": int(year),
        "Husband Age": int(h_age),
        "Wife Age": int(w_age),
        "Portfolio Balance": round(total_portfolio),
        "State Pension": round(sp_income),
        "SIPP WD": round(sipp_withdrawal),
        "ISA WD": round(isa_withdrawal),
        "Cash WD": round(cash_withdrawal),
        "Est. Tax Bill": round(tax_bill),
        "Net Spendable": round(net_pocket)
    })
    
    # Inflate withdrawal request for next year
    current_withdrawal *= (1 + inflation_rate)

df = pd.DataFrame(data)

# --- VISUALIZATION ---

st.header("📊 Financial Projections")

# Metric Row
final_balance = df.iloc[-1]['Portfolio Balance']
st.metric(label="Final Portfolio Balance (Age 95)", value=f"£{final_balance:,.0f}")

# Charts
st.subheader("Asset Depletion Over Time")
chart_data = df[['Year', 'Portfolio Balance']]
st.area_chart(chart_data.set_index('Year'))

st.subheader("Income Source Breakdown")
source_data = df[['Year', 'State Pension', 'SIPP WD', 'ISA WD', 'Cash WD']]
st.bar_chart(source_data.set_index('Year'), stack=True)

st.subheader("Detailed Schedule")
st.dataframe(df, use_container_width=True)

# Warning logic
if final_balance < 0:
    st.error("⚠️ WARNING: Based on these settings, your money will run out before age 95.")
else:
    st.success("✅ SUCCESS: Your funds are projected to last until age 95.")
  Add retirement script
