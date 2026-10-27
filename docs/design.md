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