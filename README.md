# retirement-planner
Retirement planner
# 🇬🇧 UK Retirement Withdrawal & Tax Optimiser

This dashboard calculates the maximum sustainable annual withdrawal (inflation-adjusted) from a UK portfolio comprising Cash, ISAs, and SIPPs. It solves for a target end date (e.g., Wife Age 95) and includes tax-efficiency logic.

## 🧠 Core Logic

The tool uses a binary search algorithm ("The Solver") to determine the highest gross annual spend that ensures the portfolio balance never drops below zero before the target age.

### Key Assumptions
1.  **Inflation:** Tax bands (Personal Allowance / Basic Rate Limit) and State Pensions rise with inflation.
2.  **Mortality:** Household spending drops to 70% (configurable) upon Husband's target mortality age.
3.  **Stress Testing:** Users can simulate an immediate X% drop in SIPP/ISA values to test plan robustness.

## ⚙️ Withdrawal Strategies

The dashboard offers two distinct strategies for liquidating assets. In **both** strategies, the model **always** withdraws from the SIPP first up to the available Personal Allowance (to utilise the tax-free allowance).

### 1. Growth First (Spend Cash Early)
* **Philosophy:** Maximise long-term wealth.
* **Logic:** Cash is the lowest-yielding asset (e.g., 3% vs 5% investments). This strategy burns through cash reserves immediately (after the SIPP tax-free allowance) to leave ISAs and SIPPs untouched for as long as possible, allowing them to compound.
* **Risk:** High "Sequence of Returns" risk. If markets crash early, you have no cash buffer to live on.

### 2. Safety First (Preserve Cash)
* **Philosophy:** Maximise sleep-at-night factor.
* **Logic:** Cash is retained as a "volatility buffer." The model prioritises selling ISAs first.
* **Benefit:** If the stock market crashes, you have a substantial cash pile to fund living expenses without being forced to sell equities at a loss.
* **Cost:** Lower total ending wealth due to "cash drag" (holding a low-yield asset for decades).

## 📊 Tax Optimization Rules
The model applies the following priority order to minimise tax leakage:
1.  **SIPP (Tier 1):** Withdraw enough to fill the unused Personal Allowance (Effective tax rate: ~0%).
2.  **ISA / Cash:** Withdraw based on the selected Strategy (Growth vs Safety).
3.  **SIPP (Tier 2):** If more funds are needed after exhausting ISA/Cash, withdraw from SIPP (Taxed at Basic Rate).

## 🚀 How to Run
1.  Ensure requirements are installed: `pip install streamlit pandas numpy`
2.  Run the app: `streamlit run retirement_planner.py`
