Customer Churn Analysis
Rakshit Kaushal | June 2025
This project looks at why customers are cancelling their subscriptions at a B2B SaaS company.
I was given four messy CSV files from different source systems and had to clean them,
build a data model, find the churn drivers, and present recommendations.

How to run
pip install pandas numpy
python pipeline.py
Output files will be saved to the my_output/ folder.
SQL queries are in analytical_queries.sql — written for PostgreSQL.

Files
pipeline.py                → cleans data and builds the analytical table
analytical_queries.sql     → 5 SQL queries for churn analysis
churn_analysis.ipynb       → notebook with full analysis and findings
my_output/
  dim_customers.csv
  dim_subscriptions.csv
  fact_support_tickets.csv
  fact_usage_monthly.csv
  analytical_customer_features.csv   ← this is what goes into Tableau

Data quality issues I found
Before touching anything I profiled all four files first.
Here is what was wrong:
customers.csv

30 duplicate rows — removed, kept first occurrence
35 rows had age = -5, looks like a system default — flagged and nulled
Dates were in three different formats (MM-DD-YYYY, YYYY/MM/DD, ISO) — parsed all of them
About 99 rows missing region or age — left as null, did not impute

subscriptions.csv

36 rows were marked Active but had a churn_date filled in — contradiction, nulled the date
60 rows where churn_date came before signup_date — impossible, flagged and nulled
63.7% null churn_date — this is expected, those are active customers

support_tickets.csv

20 tickets had customer_ids that dont exist in customers — flagged as orphans, excluded from joins

General

Plan and contract_type values sometimes disagreed between customers and subscriptions files
Treated subscriptions as the authoritative source, used customers as fallback

Nothing was silently fixed. Every change has a flag column showing what was done.

Data model
I went with a simple star schema:
dim_customers          one row per customer
dim_subscriptions      one row per customer
fact_support_tickets   one row per ticket
fact_usage_monthly     one row per customer per month
Then joined all four into one flat analytical table with one row per customer.
That table has 32 columns including things like tenure_days, engagement_tier,
tickets_last90d, avg_monthly_logins, and the churned flag.

What I found
Overall churn rate is 35% — 1,050 out of 3,000 customers churned.
Plan matters a lot

Basic: 42.4% churn
Standard: 32.9%
Enterprise: 28.2%
Premium: 25.8%

Basic customers churn at 1.7x the rate of Premium customers.
Contract type makes it worse
When I crossed plan with contract type the gap got much bigger:

Basic + Monthly = 47.4% churn
Premium + Annual = 14.9% churn

That is a 3x difference. You cant see this from either column alone —
you only spot it when you join the two tables together.
Early customers are the biggest problem

0 to 3 months tenure: 100% churn
3 to 6 months: 56%
6 to 12 months: 39%
12 to 24 months: 20%
Over 24 months: 6%

The 100% in the first 3 months is suspicious — it might be a recording issue
but it signals that new customers are not completing onboarding.
Low engagement = high churn
This finding needed the usage table joined to subscriptions:

Inactive customers (0 logins): 87.5% churn
Low engagement: 40.7%
Medium: 27.8%
High: 23.2%

Churned customers logged in about 25% less than active ones on average.
Acquisition channel affects retention

Paid Search: 42.9% churn
Social: 34.8%
Organic: 33.8%
Referral: 29.0%
Partner: 28.7%

Paid Search brings the most customers but they leave the fastest.

Recommendations
1. Fix onboarding for new customers
The first 3 months have catastrophic churn. Add a proper onboarding sequence —
product tour, CSM check-in at day 7 and day 30, activation milestone emails.
High confidence based on the tenure data.
2. Offer Basic Monthly customers a discount to switch to Annual
Same plan, just different contract = 13 percentage point drop in churn.
A 10-15% discount at the 30 and 90 day mark would likely pay for itself.
High confidence.
3. Flag low engagement customers early
Zero logins in 30 days should trigger an alert and re-engagement campaign.
The usage data is monthly grain right now which limits how quickly you can act —
would need more granular data for real-time intervention.
Medium confidence.
4. Shift budget from Paid Search to Referral
14 percentage point churn gap between worst and best channel.
Worth modelling LTV by channel before reallocating budget.
Medium confidence.
5. Track unresolved support tickets as a churn signal
Churned customers had 44% more tickets than active ones.
Not sure if tickets cause churn or if unhappy customers just raise more tickets —
would need time series analysis to confirm causality.
Low-medium confidence, honest limit here.

Limitations

Age data has too many bad values to use reliably in analysis
Usage is monthly grain — cant detect week-level engagement drops
No NPS or product satisfaction data — cant tell if churn is price vs product vs service
The 100% churn in 0-3 months may partly be a data recording artefact

-- 
Tableau Public Link - https://public.tableau.com/views/churn_assignment_rakshit/ChurnAssignmentDashboard?:language=en-US&publish=yes&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link

