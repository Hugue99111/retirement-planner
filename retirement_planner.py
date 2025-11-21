import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Dynamic Retirement Master", layout="wide")

st.title("🇬🇧 Dynamic Retirement Optimiser & Tax Planner")
st.markdown("""
**Status:** Fixed Logic. The solver now correctly identifies if funds run out *before* the target age.
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
h_birth_year = st.sidebar.number_input("Husband Birth Year", value=1960)
w_birth_year = st.sidebar.number_input("Wife Birth Year", value=1968)

# Calculate current ages dynamically
age_husband = current_year - h_birth_year
age_wife = current_year - w_birth_year

target_end_age = st.sidebar.number_input("Plan until Wife reaches Age", value=95)
planning_horizon = target_end_age - age_wife

st.sidebar.header("4. Economic Assumptions")
inflation_rate = st.sidebar.slider("Inflation Rate (%)", 0.0, 10.0, 3.0) / 100
isa_sipp_yield = st.sidebar.slider("Inv. Yield (50/50 Portfolio) (%)", 0.0, 10.0, 4.87) / 100
cash_yield = st.sidebar.slider("Cash Yield (%)", 0.0, 10.0, 3.0) / 100

st.sidebar.header("5. Life Events")
spending_drop_age = st.sidebar.number_input("Husband Mortality Age (Plan)", value=80)
spending_drop_percent = st.sidebar.slider("Spending Drop after Loss (%)", 50, 100, 70) / 100

# --- TAX CONSTANTS (Base Year 2025/26) ---
BASE_PERSONAL_ALLOWANCE = 12570
BASE_BASIC_RATE_LIMIT = 50270

# --- CORE CALCULATION FUNCTION ---
def run_projection(annual_gross_spend, apply_shock=True):
    
    curr_cash = cash_balance
    curr_isa = isa_balance * shock_factor if apply_shock else isa_balance
    curr_sipp = sipp_balance * shock_factor if apply_shock else sipp_balance
    
    curr_spend = annual_gross_spend
    spending_dropped = False
    ran_out_early = False # FLAG: detecting insolvency
    
    projection_data = []
    
    for i in range(int(planning_horizon) + 1):
        year = current_year + i
        h_age = age_husband + i
        w_age = age_wife + i
        
        # A. Inflate Tax Bands
        inflation_factor = (1 + inflation_rate) ** i
        personal_allowance = BASE_PERSONAL_ALLOWANCE * inflation_factor
        
        # B. Adjust Spending for Mortality
        if h_age >= spending_drop_age and not spending_dropped:
            curr_spend = curr_spend * spending_drop_percent
            spending_dropped = True
            
        # C. Calculate State Pension
        # Husband: Stops at mortality age. If mortality is 80, he gets it while 79, stops at 80.
        h_sp = 0
        if h_age >= 67 and h_age < spending_drop_age:
             h_sp = 11502 * inflation_factor
        
        # Wife: Starts at 67
        w_sp = 0
        if w_age >= 67:
            w_sp = 9202 * inflation_factor
            
        total_state_pension = h_sp + w_sp
        
        # D. Net Requirement from Portfolio
        portfolio_needed = max(0, curr_spend - total_state_pension)
        
        # E. Asset Growth (Start of Year)
        curr_cash += curr_cash * cash_yield
        curr_isa *= (1 + isa_sipp_yield)
        curr_sipp *= (1 + isa_sipp_yield)
        
        # F. Withdrawal Strategy
        remaining_needed = portfolio_needed
        
        sipp_wd = 0
        isa_wd = 0
        cash_wd = 0
        
        # 1. SIPP (Efficient Tier - Fill PA)
        total_pa = personal_allowance * (2 if h_age < spending_drop_age else 1)
        available_pa = max(0, total_pa - total_state_pension)
        optimal_tax_free_sipp = available_pa / 0.75
        
        take_sipp = min(curr_sipp, min(remaining_needed, optimal_tax_free_sipp))
        sipp_wd += take_sipp
        curr_sipp -= take_sipp
        remaining_needed -= take_sipp
        
        # 2. ISA (Tax Free)
        if remaining_needed > 0:
            take_isa = min(curr_isa, remaining_needed)
            isa_wd += take_isa
            curr_isa -= take_isa
            remaining_needed -= take_isa
            
        # 3. Cash
        if remaining_needed > 0:
            take_cash = min(curr_cash, remaining_needed)
            cash_wd += take_cash
            curr_cash -= take_cash
            remaining_needed -= take_cash
            
        # 4. SIPP (Taxable Tier - Last Resort)
        if remaining_needed > 0:
            take_sipp_excess = min(curr_sipp, remaining_needed)
            sipp_wd += take_sipp_excess
            curr_sipp -= take_sipp_excess
            remaining_needed -= take_sipp_excess
        
        # INSOLVENCY CHECK
        # If we still need money (remaining_needed > 0) but have no assets left
        if remaining_needed > 1.0: # Tolerance of £1
            ran_out_early = True
            
        # G. Tax Calculation
        taxable_income_from_sipp = sipp_wd * 0.75
        total_taxable = total_state_pension + taxable_income_from_sipp
        excess_taxable = max(0, total_taxable - total_pa)
        tax_bill = excess_taxable * 0.20
        
        total_portfolio = curr_cash + curr_isa + curr_sipp
        
        projection_data.append({
            "Year": year,
            "Husband Age": int(h_age),
            "Wife Age": int(w_age),
            "Portfolio Balance": total_portfolio,
            "Total Spend (Gross)": curr_spend,
            "State Pension": total_state_pension,
            "SIPP WD": sipp_wd,
            "ISA WD": isa_wd,
            "Cash WD": cash_wd,
            "Est. Tax": tax_bill
        })
        
        # Inflate Spend
        curr_spend *= (1 + inflation_rate)
        
    return pd.DataFrame(projection_data), total_portfolio, ran_out_early

# --- SOLVER: FIND MAX SUSTAINABLE SPEND ---
low_guess = 0.0
high_guess = 500000.0
optimized_spend = 0.0

# Binary search
for _ in range(25): # 25 iterations for high precision
    mid_guess = (low_guess + high_guess) / 2
    df_test, final_bal, ran_out = run_projection(mid_guess, apply_shock=True)
    
    if ran_out:
        # We ran out of money early -> Spend less
        high_guess = mid_guess
    else:
        # We made it to the end
        if final_bal > 0:
            # We have money left over -> Spend more
            optimized_spend = mid_guess
            low_guess = mid_guess
        else:
            # We made it but have 0 left (Unlikely to hit exact 0, but fallback)
            high_guess = mid_guess

# Run final
df_final, end_balance, ran_out_final = run_projection(optimized_spend, apply_shock=True)

# --- DASHBOARD DISPLAY ---
st.subheader(f"Recommended Annual Withdrawal (Gross): £{optimized_spend:,.0f}")
st.caption(f"Start Year: {current_year} | Market Shock Applied: {market_shock}% | Wife Target Age: {target_end_age}")

if ran_out_final:
    st.error("Warning: Even with this spend, funds may be tight in final years.")

# Graphs
st.subheader("Portfolio Depletion Curve")
st.area_chart(df_final.set_index("Year")[["Portfolio Balance"]])

st.subheader("Withdrawal Source")
st.bar_chart(df_final.set_index("Year")[["State Pension", "SIPP WD", "ISA WD", "Cash WD"]])

st.subheader("Detailed Schedule")
st.dataframe(df_final.style.format("{:,.0f}"))
