-- Churn Analysis SQL Queries
-- Tables: dim_customers, dim_subscriptions,
--         fact_support_tickets, fact_usage_monthly


-- 1. Churn rate by plan

SELECT
    plan,
    COUNT(*) AS total_customers,
    SUM(CASE WHEN status = 'Churned' THEN 1 ELSE 0 END) AS churned_customers,
    ROUND(
        100.0 * SUM(CASE WHEN status = 'Churned' THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS churn_rate_pct
FROM dim_subscriptions
GROUP BY plan
ORDER BY churn_rate_pct DESC;


-- 2. Monthly churn trend
-- Used LAG to see month over month change

WITH monthly_churn AS (
    SELECT
        DATE_TRUNC('month', churn_date) AS churn_month,
        COUNT(*) AS churned_count,
        SUM(mrr) AS mrr_lost
    FROM dim_subscriptions
    WHERE status = 'Churned'
      AND churn_date IS NOT NULL
    GROUP BY 1
)

SELECT
    churn_month,
    churned_count,
    mrr_lost,
    churned_count - LAG(churned_count) OVER (ORDER BY churn_month) AS change_vs_prev_month,
    SUM(churned_count) OVER (ORDER BY churn_month) AS cumulative_churned,
    SUM(mrr_lost) OVER (ORDER BY churn_month) AS cumulative_mrr_lost
FROM monthly_churn
ORDER BY churn_month;


-- 3. Plan vs contract type


SELECT
    COALESCE(s.plan, c.plan) AS plan_final,
    COALESCE(s.contract_type, c.contract_type) AS contract_type_final,
    COUNT(*) AS total_customers,
    SUM(CASE WHEN s.status = 'Churned' THEN 1 ELSE 0 END) AS churned_customers,
    ROUND(
        100.0 * SUM(CASE WHEN s.status = 'Churned' THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS churn_rate_pct,
    ROUND(AVG(s.mrr), 0) AS avg_mrr
FROM dim_customers c
LEFT JOIN dim_subscriptions s ON c.customer_id = s.customer_id
GROUP BY 1, 2
ORDER BY churn_rate_pct DESC;


-- 4. Ticket volume vs churn

WITH ticket_summary AS (
    SELECT
        customer_id,
        COUNT(*) AS total_tickets
    FROM fact_support_tickets
    GROUP BY customer_id
)

SELECT
    CASE
        WHEN COALESCE(t.total_tickets, 0) = 0 THEN '0 tickets'
        WHEN t.total_tickets <= 2 THEN '1-2 tickets'
        WHEN t.total_tickets <= 5 THEN '3-5 tickets'
        ELSE '6+ tickets'
    END AS ticket_bucket,
    COUNT(*) AS customers,
    ROUND(
        100.0 * SUM(CASE WHEN s.status = 'Churned' THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS churn_rate_pct
FROM dim_subscriptions s
LEFT JOIN ticket_summary t ON s.customer_id = t.customer_id
GROUP BY 1
ORDER BY churn_rate_pct DESC;


-- 5. Acquisition channel performance

SELECT
    c.acq_channel,
    COUNT(*) AS total_customers,
    ROUND(
        100.0 * SUM(CASE WHEN s.status = 'Churned' THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS churn_rate_pct,
    ROUND(
        AVG(EXTRACT(DAY FROM COALESCE(s.churn_date, CURRENT_DATE) - s.signup_date)),
        0
    ) AS avg_tenure_days,
    ROUND(AVG(s.mrr), 0) AS avg_mrr
FROM dim_customers c
LEFT JOIN dim_subscriptions s ON c.customer_id = s.customer_id
GROUP BY c.acq_channel
ORDER BY churn_rate_pct DESC;
