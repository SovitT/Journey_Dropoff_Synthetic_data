# Validation summary

Dataset folder: `data/starter`

## Row counts

| Table | Rows |
|---|---|
| cart_items | 231 |
| carts | 177 |
| customers | 250 |
| experiments | 3 |
| ground_truth | 83 |
| journey_events | 19,979 |
| journey_outcomes | 1,000 |
| orders | 99 |
| pages | 18 |
| products | 200 |
| session_experiments | 569 |
| sessions | 1,000 |
| support_tickets | 15 |

## Checks (violations must be 0)

| Group | Check | Violations | Result |
|---|---|---|---|
| Keys | customers: primary key unique | 0 | PASS |
| Keys | customers: primary key not empty | 0 | PASS |
| Keys | products: primary key unique | 0 | PASS |
| Keys | products: primary key not empty | 0 | PASS |
| Keys | pages: primary key unique | 0 | PASS |
| Keys | pages: primary key not empty | 0 | PASS |
| Keys | experiments: primary key unique | 0 | PASS |
| Keys | experiments: primary key not empty | 0 | PASS |
| Keys | sessions: primary key unique | 0 | PASS |
| Keys | sessions: primary key not empty | 0 | PASS |
| Keys | journey_events: primary key unique | 0 | PASS |
| Keys | journey_events: primary key not empty | 0 | PASS |
| Keys | carts: primary key unique | 0 | PASS |
| Keys | carts: primary key not empty | 0 | PASS |
| Keys | cart_items: primary key unique | 0 | PASS |
| Keys | cart_items: primary key not empty | 0 | PASS |
| Keys | orders: primary key unique | 0 | PASS |
| Keys | orders: primary key not empty | 0 | PASS |
| Keys | support_tickets: primary key unique | 0 | PASS |
| Keys | support_tickets: primary key not empty | 0 | PASS |
| Keys | session_experiments: primary key unique | 0 | PASS |
| Keys | session_experiments: primary key not empty | 0 | PASS |
| Keys | journey_outcomes: primary key unique | 0 | PASS |
| Keys | journey_outcomes: primary key not empty | 0 | PASS |
| Keys | ground_truth: primary key unique | 0 | PASS |
| Keys | ground_truth: primary key not empty | 0 | PASS |
| Joins | sessions.customer_id -> customers.customer_id | 0 | PASS |
| Joins | journey_events.session_id -> sessions.session_id | 0 | PASS |
| Joins | journey_events.page_id -> pages.page_id | 0 | PASS |
| Joins | journey_events.product_id -> products.product_id | 0 | PASS |
| Joins | carts.session_id -> sessions.session_id | 0 | PASS |
| Joins | cart_items.cart_id -> carts.cart_id | 0 | PASS |
| Joins | cart_items.product_id -> products.product_id | 0 | PASS |
| Joins | orders.session_id -> sessions.session_id | 0 | PASS |
| Joins | orders.cart_id -> carts.cart_id | 0 | PASS |
| Joins | orders.customer_id -> customers.customer_id | 0 | PASS |
| Joins | support_tickets.session_id -> sessions.session_id | 0 | PASS |
| Joins | support_tickets.order_id -> orders.order_id | 0 | PASS |
| Joins | support_tickets.customer_id -> customers.customer_id | 0 | PASS |
| Joins | session_experiments.session_id -> sessions.session_id | 0 | PASS |
| Joins | session_experiments.experiment_id -> experiments.experiment_id | 0 | PASS |
| Joins | journey_outcomes.session_id -> sessions.session_id | 0 | PASS |
| Allowed values | customers.consent_status | 0 | PASS |
| Allowed values | sessions.consent_status | 0 | PASS |
| Allowed values | sessions.channel | 0 | PASS |
| Allowed values | sessions.device_type | 0 | PASS |
| Allowed values | journey_events.channel | 0 | PASS |
| Allowed values | journey_events.event_type | 0 | PASS |
| Allowed values | orders.status | 0 | PASS |
| Allowed values | support_tickets.status | 0 | PASS |
| Allowed values | support_tickets.category | 0 | PASS |
| Allowed values | session_experiments.variant | 0 | PASS |
| Allowed values | journey_outcomes.outcome | 0 | PASS |
| Allowed values | ground_truth.issue_type | 0 | PASS |
| Dates | session start <= end | 0 | PASS |
| Dates | no event before its session starts | 0 | PASS |
| Dates | no event after its session ends | 0 | PASS |
| Dates | ingestion_time >= event_time | 0 | PASS |
| Dates | event_time never goes backwards as event_seq grows | 0 | PASS |
| Dates | gap between events inside a session is under 30 minutes | 0 | PASS |
| Dates | cart created inside its session | 0 | PASS |
| Dates | order placed inside its session | 0 | PASS |
| Dates | ticket resolved_time >= opened_time | 0 | PASS |
| Dates | customer signed up before the session | 0 | PASS |
| Arithmetic | order total = sum(quantity x unit_price) | 0 | PASS |
| Arithmetic | cart item price = product price | 0 | PASS |
| Arithmetic | session outcome matches its events (rule order) | 0 | PASS |
| Lifecycle | order status matches cancel/refund events | 0 | PASS |
| Lifecycle | every order has payment_completed and order_placed | 0 | PASS |
| Lifecycle | every order_placed session has an order row | 0 | PASS |
| Lifecycle | order_cancelled happens after order_placed | 0 | PASS |
| Lifecycle | ticket rows and ticket_created events agree | 0 | PASS |
| Consent | customer linked only when consent is granted | 0 | PASS |
| Consent | linked sessions are marked granted | 0 | PASS |
| Duplicates | no repeated event inside a session (same type, time, product), except labelled duplicate conversions | 0 | PASS |
| Separation | ground truth never appears in input tables | 0 | PASS |

**76 of 76 checks passed.**
