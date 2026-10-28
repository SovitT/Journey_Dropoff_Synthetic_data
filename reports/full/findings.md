# Findings

Dataset: `data/full`  |  sessions: 100,000  |  events: 2,066,472

All numbers below come from the generated data. Detection and cleaning use input columns only; `ground_truth.csv` is read once, to grade the detectors.

## 1. Can the injected problems be found?

| Problem | Detection rule | Labelled | Flagged | Correct | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| late_event | ingestion delay > 120s | 3458 | 3458 | 3458 | 1.000 | 1.000 | 1.000 |
| duplicate_conversion | 2nd+ order_placed in a session | 271 | 271 | 271 | 1.000 | 1.000 | 1.000 |
| wrong_identity_merge (per anonymous_id) | anonymous_id linked to 2+ customers | 741 | 741 | 741 | 1.000 | 1.000 | 1.000 |
| bot_traffic | >=40 events, gaps <= 2s, std <= 0.5 | 4000 | 4000 | 4000 | 1.000 | 1.000 | 1.000 |

Late events are separable because normal ingestion delay is capped at 60 s while injected delays start at 300 s (threshold 120 s). The bot rule is easy by design (fixed 1-2 s gaps); a real scraper with random pauses would need more features. Merged identities are graded per anonymous_id because the data cannot say which of the two sessions on a shared id is the wrong one.

## 2. Effect of the problems on conversion

| Method | Conversions | Sessions | Conversion rate |
|---|---|---|---|
| Raw: order_placed events / all sessions | 10,001 | 100,000 | 10.0% |
| Clean: sessions with an order / human sessions | 9,730 | 96,000 | 10.1% |

4,000 bot sessions and 271 duplicate conversion events were removed to get the clean figure. Events are ordered by `event_time`, never by `ingestion_time`.

## 3. Funnel (clean data, human sessions)

| Stage | Sessions | % of visits | Step conversion | Lost here |
|---|---|---|---|---|
| visit | 96,000 | 100.0% |  |  |
| product_view | 86,568 | 90.2% | 90.2% | 9,432 |
| add_to_cart | 17,292 | 18.0% | 20.0% | 69,276 |
| checkout | 13,046 | 13.6% | 75.4% | 4,246 |
| payment | 10,515 | 11.0% | 80.6% | 2,531 |
| order_placed | 9,730 | 10.1% | 92.5% | 785 |

The biggest loss is between product view and add to cart. Later stages lose fewer sessions in absolute terms.

## 4. Drop-off by device and app version

| channel | device_type | app_version | sessions | cart_pct | order_pct | cart_to_order_pct | crash_pct |
|---|---|---|---|---|---|---|---|
| app | android | 2.3 | 10517 | 17.4 | 9.6 | 55.0 | 6.7 |
| app | android | 2.4 | 10810 | 16.8 | 9.1 | 54.1 | 19.3 |
| app | ios | 2.3 | 8595 | 18.3 | 10.6 | 57.9 | 6.7 |
| app | ios | 2.4 | 8620 | 17.4 | 9.7 | 55.6 | 6.9 |
| web | desktop | - | 34367 | 18.4 | 10.4 | 56.6 | 0.0 |
| web | mobile_web | - | 23091 | 18.4 | 10.5 | 56.9 | 0.0 |

## 5. Friction: where people leave

Share of product views that were the session's last product view with no cart afterwards:

| product_type | product_views | left_after_view_pct |
|---|---|---|
| out_of_stock | 52578 | 52.3 |
| high_price (>60) | 28194 | 33.8 |
| normal | 328706 | 9.8 |

Orders completed among sessions that reached payment:

| group_name | sessions | completed_order_pct |
|---|---|---|
| no payment failure | 9242 | 100.0 |
| payment failed | 1273 | 38.3 |

App sessions with and without a crash:

| group_name | sessions | order_pct |
|---|---|---|
| app crash | 3969 | 8.7 |
| no crash | 34573 | 9.8 |

## 6. Experiments

| Experiment | Metric | Variant A | Variant B | B minus A | 99.2% CI | Clear effect? |
|---|---|---|---|---|---|---|
| checkout_button_color | cart -> checkout | 75.3% (n=1563) | 77.2% (n=1475) | +1.8 pts | [-2.2, +5.9] | no |
| checkout_button_color | checkout -> order | 74.9% (n=1177) | 74.9% (n=1138) | -0.1 pts | [-4.8, +4.7] | no |
| simplified_checkout | cart -> checkout | 75.0% (n=2008) | 73.9% (n=2053) | -1.1 pts | [-4.7, +2.5] | no |
| simplified_checkout | checkout -> order | 73.0% (n=1506) | 81.2% (n=1517) | +8.2 pts | [+4.2, +12.2] | yes |
| free_shipping_banner | cart -> checkout | 73.2% (n=1559) | 79.4% (n=1449) | +6.2 pts | [+2.1, +10.3] | yes |
| free_shipping_banner | checkout -> order | 74.1% (n=1141) | 75.1% (n=1150) | +1.0 pts | [-3.8, +5.8] | no |

Experiments overlap in time, so sessions can be in more than one. Intervals use a normal approximation and are widened for the 6 comparisons made (Bonferroni), so a lucky result on a metric nobody changed is less likely to look real.
