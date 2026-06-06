# Churn Analysis Pipeline
# June 2025

import pandas as pd
import numpy as np
from pathlib import Path

# pointing to raw data folder
RAW_DIR = Path("churn_data/churn_data")
OUT_DIR = Path("my_output")
OUT_DIR.mkdir(exist_ok=True)

# using June 1 as our reference date for tenure calculations
ANALYSIS_DATE = pd.Timestamp("2025-06-01")


# Step 1 - Load all 4 files

customers_raw = pd.read_csv(RAW_DIR / "customers.csv")
subs_raw      = pd.read_csv(RAW_DIR / "subscriptions.csv")
tickets_raw   = pd.read_csv(RAW_DIR / "support_tickets.csv")
usage_raw     = pd.read_csv(RAW_DIR / "usage_monthly.csv")

print("files loaded")
print(f"  customers   : {len(customers_raw)}")
print(f"  subs        : {len(subs_raw)}")
print(f"  tickets     : {len(tickets_raw)}")
print(f"  usage       : {len(usage_raw)}")


# Step 2 - Clean each table

cust  = customers_raw.copy()
subs  = subs_raw.copy()
tix   = tickets_raw.copy()
usage = usage_raw.copy()


# -- customers --

# found 30 duplicate rows, keeping first occurrence
cust = cust.drop_duplicates(subset="customer_id", keep="first")

cust["signup_date"] = pd.to_datetime(
    cust["signup_date"], format="mixed", dayfirst=False, errors="coerce"
)

# negative age values treated as invalid i.e 35 rows had age = -5

cust["age_flag"] = ""
cust.loc[cust["age"] < 0, "age_flag"] = "NEGATIVE_AGE"
cust.loc[cust["age"] < 0, "age"] = np.nan

# standardise text columns - had mixed casing
cust["plan"]          = cust["plan"].str.strip().str.title()
cust["region"]        = cust["region"].str.strip().str.title()
cust["acq_channel"]   = cust["acq_channel"].str.strip().str.title()
cust["contract_type"] = cust["contract_type"].str.strip().str.title()

print(f"\ncustomers after cleaning: {len(cust)}")


# -- subscriptions --

subs["signup_date"] = pd.to_datetime(subs["signup_date"], errors="coerce")
subs["churn_date"]  = pd.to_datetime(subs["churn_date"],  errors="coerce")

subs["plan"]          = subs["plan"].str.strip().str.title()
subs["contract_type"] = subs["contract_type"].str.strip().str.title()
subs["status"]        = subs["status"].str.strip().str.title()

subs["sub_flag"] = ""

# found 36 active customers with a churn_date 
# nulling the churn_date and flagging them
mask1 = (subs["status"] == "Active") & subs["churn_date"].notna()
subs.loc[mask1, "sub_flag"]   = "ACTIVE_WITH_CHURN_DATE"
subs.loc[mask1, "churn_date"] = pd.NaT
print(f"fixed {mask1.sum()} active rows with churn_date")

# also found cases where churn happened before signup - impossible
# flagging and removing the bad churn_date
mask2 = subs["churn_date"].notna() & (subs["churn_date"] < subs["signup_date"])
subs.loc[mask2, "sub_flag"]   = "CHURN_BEFORE_SIGNUP"
subs.loc[mask2, "churn_date"] = pd.NaT
print(f"fixed {mask2.sum()} rows where churn_date was before signup_date")


# -- tickets --

tix["created_date"] = pd.to_datetime(tix["created_date"], errors="coerce")
tix["priority"]     = tix["priority"].str.strip().str.title()
tix["category"]     = tix["category"].str.strip().str.title()
tix["resolved"]     = tix["resolved"].str.strip().str.title()

# 20 tickets had customer_ids not in our master list
#
tix["orphan_flag"] = ~tix["customer_id"].isin(cust["customer_id"])
print(f"orphan tickets flagged: {tix['orphan_flag'].sum()}")


# -- usage --

usage["month"] = pd.to_datetime(usage["month"], errors="coerce")

# clipping negatives to 0 - cant have negative logins
for col in ["logins", "features_used", "active_minutes"]:
    usage[col] = usage[col].clip(lower=0)

usage["orphan_flag"] = ~usage["customer_id"].isin(cust["customer_id"])



# Step 3 - Save dimension tables

cust.to_csv(OUT_DIR  / "dim_customers.csv",        index=False)
subs.to_csv(OUT_DIR  / "dim_subscriptions.csv",    index=False)
tix.to_csv(OUT_DIR   / "fact_support_tickets.csv", index=False)
usage.to_csv(OUT_DIR / "fact_usage_monthly.csv",   index=False)
print("\ndimension tables saved")


# Step 4 - Build features for analysis
# aggregating tickets and usage down to customer level


# usage aggregates - lifetime averages per customer
usage_clean = usage[~usage["orphan_flag"]]

usage_agg = (
    usage_clean.groupby("customer_id")
    .agg(
        avg_monthly_logins     = ("logins",         "mean"),
        avg_features_used      = ("features_used",  "mean"),
        avg_active_minutes     = ("active_minutes",  "mean"),
        total_months_with_data = ("month",           "count"),
        last_active_month      = ("month",           "max")
    )
    .reset_index()
)

usage_agg["avg_monthly_logins"] = usage_agg["avg_monthly_logins"].round(2)
usage_agg["avg_features_used"]  = usage_agg["avg_features_used"].round(2)
usage_agg["avg_active_minutes"] = usage_agg["avg_active_minutes"].round(2)

# last 90 days logins
cutoff_90 = ANALYSIS_DATE - pd.Timedelta(days=90)

usage_recent = (
    usage_clean[usage_clean["month"] >= cutoff_90]
    .groupby("customer_id")
    .agg(logins_last90d = ("logins", "sum"))
    .reset_index()
)

# ticket aggregates
tix_clean = tix[~tix["orphan_flag"]]

ticket_agg = (
    tix_clean.groupby("customer_id")
    .agg(
        total_tickets      = ("ticket_id", "count"),
        unresolved_tickets = ("resolved",  lambda x: (x == "No").sum()),
        critical_tickets   = ("priority",  lambda x: (x == "Critical").sum())
    )
    .reset_index()
)

tickets_recent = (
    tix_clean[tix_clean["created_date"] >= cutoff_90]
    .groupby("customer_id")
    .size()
    .reset_index(name="tickets_last90d")
)


# Step 5 - Join everything into one flat table

df = (
    cust
    .merge(
        subs[["customer_id","plan","mrr","contract_type",
              "signup_date","churn_date","status","sub_flag"]],
        on="customer_id", how="left", suffixes=("_cust","_sub")
    )
    .merge(usage_agg,      on="customer_id", how="left")
    .merge(usage_recent,   on="customer_id", how="left")
    .merge(ticket_agg,     on="customer_id", how="left")
    .merge(tickets_recent, on="customer_id", how="left")
)

# prefer subscription values when available
df["plan_final"]          = df["plan_sub"].combine_first(df["plan_cust"])
df["contract_type_final"] = df["contract_type_sub"].combine_first(df["contract_type_cust"])

# churn flag - 1 if churned, 0 if active
df["churned"] = (df["status"] == "Churned").astype(int)

# tenure in days
signup   = df["signup_date_sub"].combine_first(df["signup_date_cust"])
end_date = df["churn_date"].where(df["churned"] == 1, other=ANALYSIS_DATE)
df["tenure_days"] = (end_date - signup).dt.days.clip(lower=0)

# tenure buckets
bins   = [0, 90, 180, 365, 730, 9999]
labels = ["0-3m", "3-6m", "6-12m", "12-24m", "24m+"]
df["tenure_bucket"] = pd.cut(df["tenure_days"], bins=bins, labels=labels, right=False)

# engagement tier based on avg monthly logins
df["engagement_tier"] = pd.cut(
    df["avg_monthly_logins"].fillna(0),
    bins=[-1, 0, 5, 15, 9999],
    labels=["Inactive", "Low", "Medium", "High"]
)

df["days_since_last_active"] = (ANALYSIS_DATE - df["last_active_month"]).dt.days

# customers with no tickets or usage get 0 not null
zero_cols = [
    "total_tickets", "unresolved_tickets", "critical_tickets",
    "tickets_last90d", "logins_last90d", "avg_monthly_logins",
    "avg_features_used", "avg_active_minutes", "total_months_with_data"
]
df[zero_cols] = df[zero_cols].fillna(0)

# save final table
df.to_csv(OUT_DIR / "analytical_customer_features.csv", index=False)


# Summary


print("\n--- done ---")
print(f"total customers : {len(df):,}")
print(f"churned         : {df['churned'].sum():,}")
print(f"churn rate      : {df['churned'].mean()*100:.1f}%")
print(f"output folder   : {OUT_DIR.absolute()}")
