# Journey_Dropoff_Synthetic_data

# Customer journey drop-off: synthetic data generator

This project generates a reproducible synthetic dataset of web, app, support and purchase events, then validates it and analyses it to find where customers drop off and which paths have the most friction.

- **Full size:** 100,000 sessions and about 2.07 million events across web, app and support.
- **Four labelled data problems** are injected (late events, duplicate conversions, wrongly merged identities, bot traffic). Their labels live in a separate `ground_truth.csv` and are only used to grade detection.
- **Fixed seed (20261022):** running the generator twice gives byte-identical files.
- **No external data, no downloads, no services.** Everything is generated locally.

## Quick start

Needs Python 3.12 (tested) and the packages in `requirements.txt` (numpy, pandas, duckdb, pytest).

```
git clone https://github.com/SovitT/Journey_Dropoff_Synthetic_data.git
cd Journey_Dropoff_Synthetic_data
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python src/run_all.py --sessions 1000 --out data/starter
```

This takes about 15 seconds. It builds the starter dataset, validates it, writes the reports, and then rebuilds everything once more to prove the output is identical.

**Full dataset** (a few minutes, about 250 MB on disk, not stored in git):

```
python src/run_all.py --sessions 100000 --out data/full
```

Add `--skip-repro` to skip the second build and save about half the time.

**Automated checks** (under a minute):

```
python -m pytest tests -q
```

## What you get

| Where | What |
|---|---|
| `data/starter/` | 1,000-session dataset, 13 CSV files, committed to the repo |
| `data/full/` | 100,000-session dataset, created by the command above (not committed) |
| `reports/full/findings.md` | funnel, drop-off, friction, experiment results and detection scores for the full dataset |
| `reports/full/validation_summary.md` | row counts and every validation check |
| `reports/full/reproducibility.md` | hashes of two independent builds |
| `reports/starter/` | the same three reports for the starter dataset |
| `docs/design.md` | events, funnel, outcome rules, friction model, tables and assumptions |
| `docs/data_dictionary.md` | every field: type, required, allowed values, uniqueness, validation rule |
| `docs/source_manifest.md` | data provenance (none external), licences, generator command |
| `docs/AI_USAGE.md` and `prompts/` | how AI was used and the full prompt history |

## How it works

```
master_data.py   customers, products, pages, experiments
      |
journeys.py      sessions -> events -> carts -> orders -> tickets -> outcomes
      |
anomalies.py     injects the four labelled problems, writes ground_truth.csv
      |
validate.py      76 checks (keys, joins, allowed values, dates, totals, lifecycle, consent)
      |
analyze.py       detects the problems, cleans the data, reports funnel and findings
```

`src/run_all.py` runs all of this in order. `src/common.py` holds the seed, the date window and the ID formats.

Outcomes are never picked at random. Each session is simulated step by step, and the outcome is computed afterwards from the events using fixed rules:

1. `converted`: the session has an `order_placed` event
2. `support_contact`: it has a `ticket_created` event (and no order)
3. `abandoned`: it has an `add_to_cart` event (and no order)
4. `product_switch`: it viewed 2 or more different products and never added to the cart
5. `browse_only`: anything else

The first rule that matches wins.

## Main design decisions and assumptions

- **Sessions:** a visit on web or app; gaps between events inside a session stay under 15 minutes, so the 30-minute inactivity rule never splits a session. Support events happen inside the session where the problem occurred (a simplification).
- **Funnel stages:** visit, product view, add to cart, checkout, payment, order placed.
- **Identity and consent:** a customer is linked to a session only when `consent_status` is `granted`. Customers who denied consent, and visitors who never logged in, stay anonymous. Linked customers use two device IDs.
- **Event time vs ingestion time:** every event has both. Normal delay is at most 60 seconds. All analysis orders events by `event_time`.
- **Friction (the reasons people leave).** These are assumptions, written as constants at the top of `src/journeys.py`:

| Situation | Chance of leaving |
|---|---|
| Normal product view | 5% |
| Out-of-stock product | 50% |
| High-priced product (above 60) | 30% |
| Cart page (18% with the free-shipping banner, variant B) | 25% |
| Checkout (12% with simplified checkout, variant B) | 20% |
| After a payment failure | 60% |
| After an app crash | 40% |

- **Other assumptions:** 10% of sessions leave right after landing; the app crashes in 1.5% of sessions, or 5% on Android with app version 2.4; 3% of orders are cancelled and half of those refunded; a cancelled or refunded order still counts as converted because it had `order_placed`.
- **IDs:** `CUS-000001`, `SES-2026-000001`, `EVT-<session-id>-000001`, `EXP-2026-000001`, `OUT-<session-id>`, plus `PRD-`, `PAG-`, `CRT-`, `ORD-`, `TKT-` and `GT-` for the other tables.

## Injected problems and ground truth

| issue_type | What is injected | How it is found |
|---|---|---|
| `late_event` | one event per chosen session is recorded 5 minutes to 2 hours late | ingestion delay above 120 seconds |
| `duplicate_conversion` | `order_placed` recorded a second time 1 to 3 seconds later | second `order_placed` in a session |
| `wrong_identity_merge` | a session takes another customer's device ID | one device ID linked to 2 or more customers |
| `bot_traffic` | anonymous sessions replaced by scraper sessions (60 to 200 events, fixed 1 or 2 second gaps, products crawled in order) | many events with fixed tiny gaps |

Bots replace existing sessions, so the total stays at 100,000 sessions. The baseline data is never edited, and `ground_truth.csv` is a separate file that no input table or detection rule reads.

## How it was verified

- **Validation:** `src/validate.py` runs 76 SQL checks; all pass on both datasets. The injected problems are labelled data, not integrity errors, so they do not fail these checks.
- **Negative test:** `tests/test_pipeline.py` breaks an order total on purpose and confirms the validation fails. Other tests confirm that the same seed gives identical files and that ground truth stays out of the input tables.
- **Reproducibility:** `reports/*/reproducibility.md` shows file hashes of two full builds; they match.
- **Detection scoring:** `analyze.py` finds each injected problem using input columns only, then compares with the labels (precision, recall and F1 in `findings.md`).

## Results on the full dataset

Numbers from `reports/full/findings.md`:

- Clean conversion is 10.1% (9,730 orders from 96,000 human sessions); the raw data says 10.0% because bots and duplicates distort it.
- Funnel: 90.2% of visits see a product, 18.0% add to cart, 13.6% reach checkout, 10.1% order. The largest loss is between product view and add to cart.
- After viewing an out-of-stock product 52.3% of sessions leave without a cart, for a high-priced product 33.8%, for other products 9.8%.
- Android app version 2.4 crashes in 19.3% of sessions against about 7% elsewhere. App sessions with a crash order less (8.7% against 9.8%).
- Experiments: `simplified_checkout` improves checkout to order by about 8 points and `free_shipping_banner` improves cart to checkout by about 6 points, both clear after adjusting for multiple comparisons. `checkout_button_color` shows no effect.

## Limitations

- **Detection scores are perfect on purpose.** The problems are injected with clean signals, so simple rules find them. Real bots and real late data would be harder.
- **Findings recover planted patterns.** The drop-off causes were built into the generator, so the analysis shows that the pipeline can find them, not that it discovered something unknown.
- **Distributions are assumed, not fitted** to real data, because no real data was used.
- **Simplifications:** one currency, no tax, shipping or discounts, no returns beyond cancel and refund, no time zones, support happens inside the originating session, and `ticket_resolved` appears as an event only for quick in-chat resolutions (slower ones are only in `support_tickets.resolved_time`).
- **Memory:** the 100,000-session build keeps its tables in memory. Peak memory use was not measured.

## What I would do next

- Add noisy, harder-to-detect bots and a second set of anomalies with partial labels.
- Fit some distributions (session length, price, basket size) to a public dataset, with its source and licence recorded.
- Add cross-device identity stitching with a confidence score.
- Add a schema export as SQL `CREATE TABLE` statements.

## AI use

AI (Claude, in the claude.ai chat) was used throughout. See `docs/AI_USAGE.md` for what it did and what was checked, and `prompts/claude_prompt_log.md` for every prompt sent.
