# Design

## Events (things that can happen)

### Web
- page_view
- search_performed
- login_completed
- product_view
- add_to_cart
- add_to_wishlist
- checkout_started

### App
- app_open
- onboarding_view
- login_completed
- search_performed
- product_view
- add_to_cart
- app_crash

### Support
- ticket_created
- quick_help_opened
- chat_started
- support_message_sent
- faq_viewed
- ticket_resolved

### Purchase
- payment_started
- payment_method_selected
- payment_failed
- payment_completed
- order_placed
- order_cancelled
- refund_issued

Note: the same event name can happen on web or app. A "channel" field tells which.

## Funnel (the path to buying)
1. Visit: page_view / app_open
2. Product View: product_view
3. Add to Cart: add_to_cart
4. Checkout: checkout_started
5. Payment: payment_started, then payment_completed
6. Order Placed: order_placed

## Outcomes (how a session ends)
Check in this order. The first rule that matches is the outcome.

1. converted: the session has order_placed
2. support_contact: the session has ticket_created (and no order_placed)
3. abandoned: the session has add_to_cart but no order_placed
4. product_switch: the session viewed 2 or more different products, with no add_to_cart


## Tables (entities)
| Table | Primary key | Foreign keys | What it is |
|-------|-------------|--------------|------------|
| Customer | customer_id (CUS-000001) | none | A registered shopper, with consent_status (granted / denied) |
| Session | session_id (SES-2026-000001) | customer_id (optional) | One visit on web or app |
| Page | page_id (PAG-0001) | none | A web page or app screen |
| Product | product_id (PRD-0001) | none | An item for sale, with price and stock_status |
| JourneyEvent | event_id (EVT-<session_id>-000001) | session_id, page_id (optional), product_id (optional) | One action, with event_time and ingestion_time |
| Cart | cart_id (CRT-000001) | session_id | The basket in one session |
| CartItem (bridge) | cart_id + product_id | cart_id, product_id | Which products are in which cart, with quantity |
| Order | order_id (ORD-000001) | cart_id, session_id, customer_id (optional) | A completed purchase, total computed from CartItem |
| SupportTicket | ticket_id (TKT-000001) | session_id, order_id (optional), customer_id (optional) | A support case, with status |
| Experiment | experiment_id (EXP-2026-000001) | none | An A/B test |
| SessionExperiment (bridge) | session_id + experiment_id | session_id, experiment_id | Which variant (A or B) a session saw |
| JourneyOutcome | outcome_id (OUT-<session_id>) | session_id | The final result of a session |

## Relationships (cardinality)
- Customer 1:N Session (optional: anonymous sessions have no customer)
- Session 1:N JourneyEvent
- Session 1:1 Cart (optional), Cart 1:1 Order (optional)
- Cart N:M Product through CartItem
- Session N:M Experiment through SessionExperiment
- Session 1:1 JourneyOutcome
- Session 1:N SupportTicket (optional)

## Sessionization rules
- A new session starts after 30 minutes with no events.
- A session belongs to one device and one channel (web or app).
- Support events join the session where the problem happened if it was within 24 hours. Otherwise they form their own support session.
- Session time is based on event_time (when it happened), not ingestion_time (when it was recorded).

## Identity and consent
- Every session has an anonymous_id.
- customer_id is attached only if the customer logged in and consent_status is granted.
- Without consent, sessions stay anonymous, even for a known customer.
- One customer can have several anonymous_ids (phone, laptop). They are linked only with consent.

## Anomalies to inject (labelled in ground_truth)
| issue_type | What I inject | How it is detected |
|------------|---------------|--------------------|
| late_event | Some events get a large delay, so ingestion order differs from event order | Compare event_time and ingestion_time ordering |
| wrong_identity_merge | One anonymous_id wrongly linked to two customers | Check that each anonymous_id maps to one customer |
| duplicate_conversion | An order_placed event is recorded twice | Deduplicate by order_id and compare conversion counts |
| bot_traffic | Sessions with no consent, very fast and even event timing | Bot flag from features, scored against ground_truth |

## Generation settings
- Fixed seed: 20261022
- Full size: 100,000 sessions, about 2 million events
- One generator, with a --sessions option (for example 1,000 for a small test)
- Fixed date window (my assumption): 2026-01-01 to 2026-03-31
- ground_truth.csv is a separate file and is never used by the metrics

## Validation checks
- Primary keys are unique
- Every foreign key points to a real parent row
- Event types and statuses use allowed values only
- No event happens before its session starts
- Order total equals the sum of its CartItem rows
- Running twice with the same seed gives identical files

## Changes made while building
- Three extra web/app events were added to reach realistic volume: filter_applied, product_image_view, review_viewed.
- Support events happen inside the same session as the problem (a simplification of the 24-hour rule).
- ticket_resolved is an event only for fast in-chat resolutions. Slower ones are recorded only in SupportTicket.resolved_time.
- A cancelled or refunded order still counts as "converted" because it had order_placed. Its final status is in the Order table.