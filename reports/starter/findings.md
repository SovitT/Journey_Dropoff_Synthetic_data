# Findings

Dataset: `data/starter`  |  sessions: 1,000  |  events: 19,979

All numbers below come from the generated data. Detection and cleaning use input columns only; `ground_truth.csv` is read once, to grade the detectors.

## 1. Can the injected problems be found?

| Problem | Detection rule | Labelled | Flagged | Correct | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| late_event | ingestion delay > 120s | 34 | 34 | 34 | 1.000 | 1.000 | 1.000 |
| duplicate_conversion | 2nd+ order_placed in a session | 2 | 2 | 2 | 1.000 | 1.000 | 1.000 |
| wrong_identity_merge (per anonymous_id) | anonymous_id linked to 2+ customers | 7 | 7 | 7 | 1.000 | 1.000 | 1.000 |
| bot_traffic | >=40 events, gaps <= 2s, std <= 0.5 | 40 | 40 | 40 | 1.000 | 1.000 | 1.000 |

Late events are separable because normal ingestion delay is capped at 60 s while injected delays start at 300 s (threshold 120 s). The bot rule is easy by design (fixed 1-2 s gaps); a real scraper with random pauses would need more features. Merged identities are graded per anonymous_id because the data cannot say which of the two sessions on a shared id is the wrong one.

## 2. Effect of the problems on conversion

| Method | Conversions | Sessions | Conversion rate |
|---|---|---|---|
| Raw: order_placed events / all sessions | 101 | 1,000 | 10.1% |
| Clean: sessions with an order / human sessions | 99 | 960 | 10.3% |

40 bot sessions and 2 duplicate conversion events were removed to get the clean figure. Events are ordered by `event_time`, never by `ingestion_time`.

## 3. Funnel (clean data, human sessions)

| Stage | Sessions | % of visits | Step conversion | Lost here |
|---|---|---|---|---|
| visit | 960 | 100.0% |  |  |
| product_view | 851 | 88.6% | 88.6% | 109 |
| add_to_cart | 177 | 18.4% | 20.8% | 674 |
| checkout | 135 | 14.1% | 76.3% | 42 |
| payment | 105 | 10.9% | 77.8% | 30 |
| order_placed | 99 | 10.3% | 94.3% | 6 |

The biggest loss is between product view and add to cart. Later stages lose fewer sessions in absolute terms.

## 4. Drop-off by device and app version

| channel | device_type | app_version | sessions | cart_pct | order_pct | cart_to_order_pct | crash_pct |
|---|---|---|---|---|---|---|---|
| app | android | 2.3 | 96 | 19.8 | 8.3 | 42.1 | 7.3 |
| app | android | 2.4 | 109 | 15.6 | 9.2 | 58.8 | 22.9 |
| app | ios | 2.3 | 82 | 19.5 | 17.1 | 87.5 | 6.1 |
| app | ios | 2.4 | 86 | 14.0 | 8.1 | 58.3 | 8.1 |
| web | desktop | - | 355 | 19.2 | 9.9 | 51.5 | 0.0 |
| web | mobile_web | - | 232 | 19.4 | 10.8 | 55.6 | 0.0 |

## 5. Friction: where people leave

Share of product views that were the session's last product view with no cart afterwards:

| product_type | product_views | left_after_view_pct |
|---|---|---|
| out_of_stock | 151 | 53.0 |
| high_price (>60) | 849 | 33.9 |
| normal | 2904 | 10.5 |

Orders completed among sessions that reached payment:

| group_name | sessions | completed_order_pct |
|---|---|---|
| no payment failure | 97 | 100.0 |
| payment failed | 8 | 25.0 |

App sessions with and without a crash:

| group_name | sessions | order_pct |
|---|---|---|
| app crash | 44 | 4.5 |
| no crash | 329 | 11.2 |

## 6. Experiments

| Experiment | Metric | Variant A | Variant B | B minus A | 99.2% CI | Clear effect? |
|---|---|---|---|---|---|---|
| checkout_button_color | cart -> checkout | 76.5% (n=17) | 70.6% (n=17) | -5.9 pts | [-45.7, +34.0] | no |
| checkout_button_color | checkout -> order | 53.8% (n=13) | 91.7% (n=12) | +37.8 pts | [-4.3, +79.9] | no |
| simplified_checkout | cart -> checkout | 88.2% (n=17) | 90.9% (n=22) | +2.7 pts | [-23.5, +28.9] | no |
| simplified_checkout | checkout -> order | 86.7% (n=15) | 85.0% (n=20) | -1.7 pts | [-33.0, +29.6] | no |
| free_shipping_banner | cart -> checkout | 78.3% (n=23) | 54.5% (n=11) | -23.7 pts | [-69.4, +21.9] | no |
| free_shipping_banner | checkout -> order | 77.8% (n=18) | 66.7% (n=6) | -11.1 pts | [-68.1, +45.9] | no |

Experiments overlap in time, so sessions can be in more than one. Intervals use a normal approximation and are widened for the 6 comparisons made (Bonferroni), so a lucky result on a metric nobody changed is less likely to look real.
