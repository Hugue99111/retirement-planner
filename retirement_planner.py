import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Dynamic Retirement Master", layout="wide")

st.title("🇬🇧 Dynamic Retirement Optimiser & Tax Planner")
st.markdown("""
**Status:** Updated with Strategy Selector. Choose between **Safety** (Keep Cash) or **Growth** (Spend Cash).
""")

# --- SIDEBAR: INPUTS & VARIABLES ---

st.sidebar.header("1. Strategy Settings")
strategy_mode = st.sidebar.radio(
    "Withdrawal Priority",
    ("Safety First (Preserve Cash)", "Growth First (Spend Cash Early)"),
    help="Safety keeps cash as a buffer. Growth spends cash first to let ISAs compound."
)

st.sidebar.header("2. Current Status (Update Annually)")
current_year = st.sidebar.number_input("Current Calendar Year", value=2025, step=1)
cash_balance = st.sidebar.number_input("Current Cash Balance (£)", value=307000, step=1000)
isa_balance = st.sidebar.number_input("Current ISA Balance (£)", value=800000, step=5000)
sipp_balance = st.sidebar.number_input("Current SIPP Balance (£)", value=800000, step=5000)

st.sidebar.header("3. Stress Test (Buffer)")
market_shock = st.sidebar.slider("Simulate Immediate Market Drop (%)", 0, 50, 0, help="Reduces SIPP/ISA value immediately to test safety.")
shock_factor = 1 - (market_shock / 100.0)

st.sidebar.header("4. Personal Details")
h_birth_year = st.sidebar.number_input("Husband Birth Year", value=1960)
w_birth_year = st.sidebar.number_input("Wife Birth Year", value=1968)

age_husband = current_year - h_birth_year
age_wife = current_year - w_birth_year
target_end_age = st.sidebar.number_input("Plan until Wife reaches Age", value=95)
planning_horizon = target_end_age - age_wife

st.sidebar.header("5. Economic Assumptions")
inflation_rate = st.sidebar.slider("Inflation Rate (%)", 0.0, 10.0, 3.0) / 100
isa_sipp_yield = st.sidebar.slider("Inv. Yield (50/50 Portfolio) (%)", 0.0, 10.0, 4.87) / 100
cash_yield = st.sidebar.slider("Cash Yield (%)", 0.0, 10.0, 3.0) / 100

st.sidebar.header("6. Life Events")
spending_drop_age = st.sidebar.number_input("Husband Mortality Age (Plan)", value=80)
spending_drop_percent = st.sidebar.slider("Spending Drop after Loss (%)", 50, 100, 70) / 100

# --- TAX CONSTANTS ---
BASE_PERSONAL_ALLOWANCE = 12570
BASE_BASIC_RATE_LIMIT = 50270

# --- CORE CALCULATION FUNCTION ---
def run_projection(annual_gross_spend, apply_shock=True):
    
    curr_cash = cash_balance
    curr_isa = isa_balance * shock_factor if apply_shock else isa_balance
    curr_sipp = sipp_balance * shock_factor if apply_shock else sipp_balance
    
    curr_spend = annual_gross_spend
    spending_dropped = False
    ran_out_early = False 
    
    projection_data = []
    
    for i in range(int(planning_horizon) + 1):
        year = current_year + i
        h_age = age_husband + i
        w_age = age_wife + i
        
        # Inflate Tax Bands
        inflation_factor = (1 + inflation_rate) ** i
        personal_allowance = BASE_PERSONAL_ALLOWANCE * inflation_factor
        
        # Mortality Adjustment
        if h_age >= spending_drop_age and not spending_dropped:
            curr_spend = curr_spend * spending_drop_percent
            spending_dropped = True
            
        # State Pension
        h_sp = 0
        if h_age >= 67 and h_age < spending_drop_age:
             h_sp = 11502 * inflation_factor
        w_sp = 0
        if w_age >= 67:
            w_sp = 9202 * inflation_factor
        total_state_pension = h_sp + w_sp
        
        # Net Portfolio Requirement
        portfolio_needed = max(0, curr_spend - total_state_pension)
        
        # Asset Growth
        curr_cash += curr_cash * cash_yield
        curr_isa *= (1 + isa_sipp_yield)
        curr_sipp *= (1 + isa_sipp_yield)
        
        # --- WITHDRAWAL LOGIC ---
        remaining_needed = portfolio_needed
        sipp_wd = 0
        isa_wd = 0
        cash_wd = 0
        
        # Step 1 (Universal): ALWAYS use SIPP to fill Personal Allowance ("Use it or lose it")
        total_pa = personal_allowance * (2 if h_age < spending_drop_age else 1)
        available_pa = max(0, total_pa - total_state_pension)
        optimal_tax_free_sipp = available_pa / 0.75
        
        take_sipp = min(curr_sipp, min(remaining_needed, optimal_tax_free_sipp))
        sipp_wd += take_sipp
        curr_sipp -= take_sipp
        remaining_needed -= take_sipp
        
        # Step 2: Choose Strategy for the rest
        if strategy_mode == "Growth First (Spend Cash Early)":
            # Priority: Cash -> ISA -> SIPP (Taxable)
            
            # Cash
            if remaining_needed > 0:
                take_cash = min(curr_cash, remaining_needed)
                cash_wd += take_cash
                curr_cash -= take_cash
                remaining_needed -= take_cash
            
            # ISA
            if remaining_needed > 0:
                take_isa = min(curr_isa, remaining_needed)
                isa_wd += take_isa
                curr_isa -= take_isa
                remaining_needed -= take_isa
                
        else: # Safety First (Preserve Cash)
            # Priority: ISA -> SIPP (Taxable) -> Cash (Last Resort)
            
            # ISA
            if remaining_needed > 0:
                take_isa = min(curr_isa, remaining_needed)
                isa_wd += take_isa
                curr_isa -= take_isa
                remaining_needed -= take_isa
        
        # Step 3: Fill any remaining gap (Usually SIPP Taxable or final Cash scraps)
        if remaining_needed > 0:
            # If Growth Strategy, we already used Cash/ISA. Must use SIPP Taxable.
            # If Safety Strategy, we used ISA. Now try SIPP Taxable, then Cash.
            
            if strategy_mode == "Safety First (Preserve Cash)":
                # Try SIPP (Taxable) before touching Cash stockpile
                 take_sipp_excess = min(curr_sipp, remaining_needed)
                 sipp_wd += take_sipp_excess
                 curr_sipp -= take_sipp_excess
                 remaining_needed -= take_sipp_excess
                 
                 # If still needed, finally touch Cash
                 if remaining_needed > 0:
                     take_cash = min(curr_cash, remaining_needed)
                     cash_wd += take_cash
                     curr_cash -= take_cash
                     remaining_needed -= take_cash
            else:
                 # Growth strategy: We already burned Cash and ISA. Only SIPP left.
                 take_sipp_excess = min(curr_sipp, remaining_needed)
                 sipp_wd += take_sipp_excess
                 curr_sipp -= take_sipp_excess
                 remaining_needed -= take_sipp_excess

        # Check Insolvency
        if remaining_needed > 1.0: 
            ran_out_early = True
            
        # Tax Calc
        taxable_income_from_sipp = sipp_wd * 0.75
        total_taxable = total_state_pension + taxable_income_from_sipp
        excess_taxable = max(0, total_taxable - total_pa)
        tax_bill = excess_taxable * 0.20
        
        total_portfolio = curr_cash + curr_isa + curr_sipp
        
        projection_data.append({
            "Year": year,
            "Portfolio Balance": total_portfolio,
            "Total Spend (Gross)": curr_spend,
            "State Pension": total_state_pension,
            "SIPP WD": sipp_wd,
            "ISA WD": isa_wd,
            "Cash WD": cash_wd,
            "Est. Tax": tax_bill
        })
        
        curr_spend *= (1 + inflation_rate)
        
    return pd.DataFrame(projection_data), total_portfolio, ran_out_early

# --- SOLVER ---
low_guess = 0.0
high_guess = 500000.0
optimized_spend = 0.0

for _ in range(20):
    mid_guess = (low_guess + high_guess) / 2
    df_test, final_bal, ran_out = run_projection(mid_guess, apply_shock=True)
    if ran_out:
        high_guess = mid_guess
    else:
        if final_bal > 0:
            optimized_spend = mid_guess
            low_guess = mid_guess
        else:
            high_guess = mid_guess

df_final, end_balance, ran_out_final = run_projection(optimized_spend, apply_shock=True)

# --- DASHBOARD ---
st.subheader(f"Recommended Annual Withdrawal (Gross): £{optimized_spend:,.0f}")
st.caption(f"Strategy: {strategy_mode} | Market Shock: {market_shock}%")

col1, col2 = st.columns(2)
with col1:
    st.area_chart(df_final.set_index("Year")[["Portfolio Balance"]])
with col2:
    st.bar_chart(df_final.set_index("Year")[["State Pension", "SIPP WD", "ISA WD", "Cash WD"]])

st.dataframe(df_final.style.format("{:,.0f}"))
