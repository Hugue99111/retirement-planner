import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Dynamic Retirement Master", layout="wide")

st.title("🇬🇧 Dynamic Retirement Optimiser & Tax Planner")
st.markdown("""
**How to use for Annual Review:**
1. Update the **Current Year** and your **Current Balances**.
2. Set your **Stress Test** (Market Crash Buffer).
3. The tool automatically solves for your maximum safe **Gross Annual Spend**.
""")

# --- SIDEBAR: INPUTS & VARIABLES ---

st.sidebar.header("1. Current Status (Update Annually)")
current_year = st.sidebar.number_input("Current Calendar Year", value=2025, step=1)
cash_balance = st.sidebar.number_input("Current Cash Balance (£)", value=307000, step=1000)
isa_balance = st.sidebar.number_input("Current ISA Balance (£)", value=800000, step=5000)
sipp_balance = st.sidebar.number_input("Current SIPP Balance (£)", value=800000, step=5000)

st.sidebar.header("2. Stress Test (Buffer)")
market_shock = st.sidebar.slider("Simulate Immediate Market Drop (%)", 0, 50, 0, help="Reduces SIPP/ISA value immediately to test safety.")
shock_factor = 1 - (market_shock / 100.0)

st.sidebar.header("3. Personal Details")
# Ages are calculated based on the Current Year relative to base birth years
# Assuming Husband born ~1960 (64 in 2024) and Wife born ~1968 (56 in 2024)
h_birth_year = st.sidebar.number_input("Husband Birth Year", value=1960)
w_birth_year = st.sidebar.number_input("Wife Birth Year", value=1968)

# Calculate current ages dynamically
age_husband = current_year - h_birth_year
age_wife = current_year - w_birth_year

target_end_age = st.sidebar.number_input("Plan until Wife reaches Age", value=95)
planning_horizon = target_end_age - age_wife

st.sidebar.header("4. Economic Assumptions")
inflation_rate = st.sidebar.slider("Inflation Rate (%)", 0.0, 10.0, 3.0) / 100
# 50/50 Split implication: slightly lower yield than pure equity
isa_sipp_yield = st.sidebar.slider("Inv. Yield (50/50 Portfolio) (%)", 0.0, 10.0, 4.87) / 100
cash_yield = st.sidebar.slider("Cash Yield (%)", 0.0, 10.0, 3.0) / 100

st.sidebar.header("5. Life Events")
spending_drop_age = st.sidebar.number_input("Husband Mortality Age (Plan)", value=80)
spending_drop_percent = st.sidebar.slider("Spending Drop after Loss (%)", 50, 100, 70) / 100

# --- TAX CONSTANTS (Base Year 2025/26) ---
# We assume these rise with inflation to keep "Real" values consistent
BASE_PERSONAL_ALLOWANCE = 12570
BASE_BASIC_RATE_LIMIT = 50270
TAX_FREE_SIPP_PCT = 0.25

# --- CORE CALCULATION FUNCTION ---
def run_projection(annual_gross_spend, apply_shock=True):
    
    # Apply Shock if strictly requested (for start of simulation)
    curr_cash = cash_balance
    curr_isa = isa_balance * shock_factor if apply_shock else isa_balance
    curr_sipp = sipp_balance * shock_factor if apply_shock else sipp_balance
    
    curr_spend = annual_gross_spend
    spending_dropped = False
    
    projection_data = []
    
    for i in range(planning_horizon + 1):
        year = current_year + i
        h_age = age_husband + i
        w_age = age_wife + i
        
        # A. Inflate Tax Bands (Assumption: Bands rise with inflation)
        inflation_factor = (1 + inflation_rate) ** i
        personal_allowance = BASE_PERSONAL_ALLOWANCE * inflation_factor
        basic_rate_limit = BASE_BASIC_RATE_LIMIT * inflation_factor
        
        # B. Adjust Spending for Mortality
        if h_age >= spending_drop_age and not spending_dropped:
            curr_spend = curr_spend * spending_drop_percent
            spending_dropped = True
            
        # C. Calculate State Pension
        # Husband: Stops at mortality age
        h_sp = 0
        if h_age >= 67 and h_age < spending_drop_age:
             h_sp = 11502 * inflation_factor
        
        # Wife: Starts at 67, continues until end
        w_sp = 0
        if w_age >= 67:
            w_sp = 9202 * inflation_factor
            
        total_state_pension = h_sp + w_sp
        
        # D. Net Requirement from Portfolio
        # We need to generate (Spend - State Pension)
        portfolio_needed = max(0, curr_spend - total_state_pension)
        
        # E. Asset Growth (Start of Year)
        cash_interest = curr_cash * cash_yield
        curr_cash += cash_interest
        curr_isa *= (1 + isa_sipp_yield)
        curr_sipp *= (1 + isa_sipp_yield)
        
        # F. Withdrawal Strategy (Tax Optimised)
        remaining_needed = portfolio_needed
        
        sipp_wd = 0
        isa_wd = 0
        cash_wd = 0
        
        # Strategy 1: Calculate "Tax Efficient" SIPP amount
        # We want to use SIPP to fill the Personal Allowance (PA).
        # Taxable Income = 75% of SIPP WD.
        # Target Taxable = PA gap.
        # Gap depends on if husband is alive.
        
        # Available PA for SIPP offsetting
        # If Husband alive: We have 2 PAs. Husband uses his for his pension? 
        # Simplified: We pool allowances.
        
        total_pa = personal_allowance * (2 if h_age < spending_drop_age else 1)
        
        # State pension consumes some PA
        available_pa = max(0, total_pa - total_state_pension)
        
        # Gross SIPP WD needed to fill this PA gap (75% is taxable)
        # WD * 0.75 = available_pa  => WD = available_pa / 0.75
        optimal_tax_free_sipp = available_pa / 0.75
        
        # Take SIPP (Efficient Tier)
        take_sipp = min(curr_sipp, min(remaining_needed, optimal_tax_free_sipp))
        sipp_wd += take_sipp
        curr_sipp -= take_sipp
        remaining_needed -= take_sipp
        
        # Strategy 2: Take ISA (Tax Free)
        if remaining_needed > 0:
            take_isa = min(curr_isa, remaining_needed)
            isa_wd += take_isa
            curr_isa -= take_isa
            remaining_needed -= take_isa
            
        # Strategy 3: Take Cash
        if remaining_needed > 0:
            take_cash = min(curr_cash, remaining_needed)
            cash_wd += take_cash
            curr_cash -= take_cash
            remaining_needed -= take_cash
            
        # Strategy 4: SIPP (Taxable Tier) - Only if desperate
        if remaining_needed > 0:
            take_sipp_excess = min(curr_sipp, remaining_needed)
            sipp_wd += take_sipp_excess
            curr_sipp -= take_sipp_excess
            remaining_needed -= take_sipp_excess
            
        # G. Tax Calculation
        taxable_income_from_sipp = sipp_wd * 0.75
        # Total Taxable = State Pension + Taxable SIPP
        total_taxable = total_state_pension + taxable_income_from_sipp
        
        # Deduct PA
        excess_taxable = max(0, total_taxable - total_pa)
        tax_bill = excess_taxable * 0.20 # Basic Rate Assumption
        
        total_portfolio = curr_cash + curr_isa + curr_sipp
        
        # Record Data
        projection_data.append({
            "Year": year,
            "Husband Age": h_age,
            "Wife Age": w_age,
            "Portfolio Balance": total_portfolio,
            "Total Spend (Gross)": round(curr_spend),
            "State Pension": round(total_state_pension),
            "SIPP WD": round(sipp_wd),
            "ISA WD": round(isa_wd),
            "Cash WD": round(cash_wd),
            "Est. Tax": round(tax_bill),
            "Net Spendable Income": round(curr_spend - tax_bill)
        })
        
        # Inflate Spend for next year
        curr_spend *= (1 + inflation_rate)
        
    return pd.DataFrame(projection_data), total_portfolio

# --- SOLVER: FIND MAX SUSTAINABLE SPEND ---
# Binary Search to find the highest spend that leaves > £0 at end
low_guess = 0
high_guess = 500000
optimized_spend = 0

# We iterate 20 times to find precision
for _ in range(20):
    mid_guess = (low_guess + high_guess) / 2
    df_test, final_bal = run_projection(mid_guess, apply_shock=True)
    
    if final_bal >= 0:
        optimized_spend = mid_guess
        low_guess = mid_guess
    else:
        high_guess = mid_guess

# Run final projection with optimized number
df_final, end_balance = run_projection(optimized_spend, apply_shock=True)

# --- DASHBOARD DISPLAY ---

st.subheader(f"Recommended Annual Withdrawal (Gross): £{optimized_spend:,.0f}")
st.caption(f"This amount is inflation-indexed. It assumes a {market_shock}% market drop happens immediately.")

col1, col2 = st.columns(2)
with col1:
    st.info(f"**Wife's End Age:** {target_end_age}")
with col2:
    st.info(f"**Portfolio Shock:** -{market_shock}% applied")

# Graphs
st.subheader("Portfolio Depletion Curve")
st.area_chart(df_final.set_index("Year")[["Portfolio Balance"]])

st.subheader("Withdrawal Source & Tax Plan")
st.bar_chart(df_final.set_index("Year")[["State Pension", "SIPP WD", "ISA WD", "Cash WD"]])

st.subheader("Detailed Tax Schedule (Next 10 Years)")
st.dataframe(df_final.head(10).style.format("{:,.0f}"))

st.markdown("---")
st.subheader("📝 For Your Tax Return (Self Assessment)")
st.markdown("""
Use the table above to guide your withdrawals. When filling out your UK Self Assessment:
1. **P60 / Private Pensions:** Sum the `State Pension` and `SIPP WD` columns for the tax year. 
   *Note: Only 75% of the SIPP WD is taxable, but your provider usually reports the taxable amount on the P60.*
2. **ISA Withdrawals:** Do **not** declare these. They are invisible to HMRC.
3. **Cash Interest:** You must declare interest earned on your Cash holdings if it exceeds your Personal Savings Allowance (£1,000 for Basic Rate taxpayers).
""")
