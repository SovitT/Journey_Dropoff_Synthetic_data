import argparse
import sys
from pathlib import Path

import duckdb

PRIMARY_KEYS = {
    "customers": "customer_id", "products": "product_id", "pages": "page_id",
    "experiments": "experiment_id", "sessions": "session_id",
    "journey_events": "event_id", "carts": "cart_id",
    "cart_items": "cart_id, product_id", "orders": "order_id",
    "support_tickets": "ticket_id",
    "session_experiments": "session_id, experiment_id",
    "journey_outcomes": "outcome_id", "ground_truth": "issue_id"}

# (child table, child column, parent table, parent column)
FOREIGN_KEYS = [
    ("sessions", "customer_id", "customers", "customer_id"),
    ("journey_events", "session_id", "sessions", "session_id"),
    ("journey_events", "page_id", "pages", "page_id"),
    ("journey_events", "product_id", "products", "product_id"),
    ("carts", "session_id", "sessions", "session_id"),
    ("cart_items", "cart_id", "carts", "cart_id"),
    ("cart_items", "product_id", "products", "product_id"),
    ("orders", "session_id", "sessions", "session_id"),
    ("orders", "cart_id", "carts", "cart_id"),
    ("orders", "customer_id", "customers", "customer_id"),
    ("support_tickets", "session_id", "sessions", "session_id"),
    ("support_tickets", "order_id", "orders", "order_id"),
    ("support_tickets", "customer_id", "customers", "customer_id"),
    ("session_experiments", "session_id", "sessions", "session_id"),
    ("session_experiments", "experiment_id", "experiments", "experiment_id"),
    ("journey_outcomes", "session_id", "sessions", "session_id")]

EVENT_TYPES = [
    "page_view", "app_open", "onboarding_view", "login_completed",
    "search_performed", "filter_applied", "product_view", "product_image_view",
    "review_viewed", "add_to_cart", "add_to_wishlist", "checkout_started",
    "payment_method_selected", "payment_started", "payment_failed",
    "payment_completed", "order_placed", "order_cancelled", "refund_issued",
    "app_crash", "faq_viewed", "quick_help_opened", "chat_started",
    "support_message_sent", "ticket_created", "ticket_resolved"]

ENUMS = [
    ("customers", "consent_status", ["granted", "denied"]),
    ("sessions", "consent_status", ["granted", "denied", "not_logged_in"]),
    ("sessions", "channel", ["web", "app"]),
    ("sessions", "device_type", ["desktop", "mobile_web", "ios", "android"]),
    ("journey_events", "channel", ["web", "app", "support"]),
    ("journey_events", "event_type", EVENT_TYPES),
    ("orders", "status", ["placed", "cancelled", "refunded"]),
    ("support_tickets", "status", ["open", "resolved"]),
    ("support_tickets", "category",
     ["payment_issue", "app_issue", "order_issue", "general"]),
    ("session_experiments", "variant", ["A", "B"]),
    ("journey_outcomes", "outcome",
     ["converted", "support_contact", "abandoned", "product_switch",
      "browse_only"]),
    ("ground_truth", "issue_type",
     ["late_event", "duplicate_conversion", "wrong_identity_merge",
      "bot_traffic"])]

TS = "CAST({} AS TIMESTAMP)"


def build_checks():
    """Returns (group, name, sql) where sql counts violations."""
    checks = []
    for t, pk in PRIMARY_KEYS.items():
        checks.append(("Keys", f"{t}: primary key unique",
                       f"SELECT COUNT(*) FROM (SELECT {pk} FROM {t} "
                       f"GROUP BY {pk} HAVING COUNT(*) > 1)"))
        first = pk.split(",")[0]
        checks.append(("Keys", f"{t}: primary key not empty",
                       f"SELECT COUNT(*) FROM {t} WHERE {first} IS NULL"))
    for c, cc, p, pc in FOREIGN_KEYS:
        checks.append(("Joins", f"{c}.{cc} -> {p}.{pc}",
                       f"SELECT COUNT(*) FROM {c} x LEFT JOIN {p} y "
                       f"ON x.{cc} = y.{pc} "
                       f"WHERE x.{cc} IS NOT NULL AND y.{pc} IS NULL"))
    for t, col, allowed in ENUMS:
        vals = ", ".join(f"'{a}'" for a in allowed)
        checks.append(("Allowed values", f"{t}.{col}",
                       f"SELECT COUNT(*) FROM {t} WHERE {col} IS NULL "
                       f"OR {col} NOT IN ({vals})"))

    ev, ss = TS.format("e.event_time"), TS.format("s.start_time")
    checks += [
        ("Dates", "session start <= end",
         f"SELECT COUNT(*) FROM sessions WHERE {TS.format('start_time')} "
         f"> {TS.format('end_time')}"),
        ("Dates", "no event before its session starts",
         f"SELECT COUNT(*) FROM journey_events e JOIN sessions s USING "
         f"(session_id) WHERE {ev} < {ss}"),
        ("Dates", "no event after its session ends",
         f"SELECT COUNT(*) FROM journey_events e JOIN sessions s USING "
         f"(session_id) WHERE {ev} > {TS.format('s.end_time')}"),
        ("Dates", "ingestion_time >= event_time",
         f"SELECT COUNT(*) FROM journey_events WHERE "
         f"{TS.format('ingestion_time')} < {TS.format('event_time')}"),
        ("Dates", "event_time never goes backwards as event_seq grows",
         "SELECT COUNT(*) FROM (SELECT event_time, LAG(event_time) OVER "
         "(PARTITION BY session_id ORDER BY CAST(event_seq AS INT)) AS prev "
         f"FROM journey_events) WHERE {TS.format('event_time')} < "
         f"{TS.format('prev')}"),
        ("Dates", "gap between events inside a session is under 30 minutes",
         "SELECT COUNT(*) FROM (SELECT epoch(" + TS.format("event_time")
         + ") - LAG(epoch(" + TS.format("event_time") + ")) OVER "
         "(PARTITION BY session_id ORDER BY CAST(event_seq AS INT)) AS gap "
         "FROM journey_events) WHERE gap >= 1800"),
        ("Dates", "cart created inside its session",
         f"SELECT COUNT(*) FROM carts c JOIN sessions s USING (session_id) "
         f"WHERE {TS.format('c.created_time')} NOT BETWEEN {ss} AND "
         f"{TS.format('s.end_time')}"),
        ("Dates", "order placed inside its session",
         f"SELECT COUNT(*) FROM orders o JOIN sessions s USING (session_id) "
         f"WHERE {TS.format('o.order_time')} NOT BETWEEN {ss} AND "
         f"{TS.format('s.end_time')}"),
        ("Dates", "ticket resolved_time >= opened_time",
         f"SELECT COUNT(*) FROM support_tickets WHERE resolved_time IS NOT "
         f"NULL AND {TS.format('resolved_time')} < {TS.format('opened_time')}"),
        ("Dates", "customer signed up before the session",
         f"SELECT COUNT(*) FROM sessions s JOIN customers c USING "
         f"(customer_id) WHERE CAST(c.signup_date AS DATE) > "
         f"CAST(s.start_time AS DATE)"),
    ]

    checks += [
        ("Arithmetic", "order total = sum(quantity x unit_price)",
         "SELECT COUNT(*) FROM orders o JOIN (SELECT cart_id, "
         "SUM(CAST(quantity AS INT) * CAST(unit_price AS DOUBLE)) AS t "
         "FROM cart_items GROUP BY cart_id) i USING (cart_id) "
         "WHERE ABS(CAST(o.total_amount AS DOUBLE) - i.t) > 0.011"),
        ("Arithmetic", "cart item price = product price",
         "SELECT COUNT(*) FROM cart_items i JOIN products p USING "
         "(product_id) WHERE ABS(CAST(i.unit_price AS DOUBLE) - "
         "CAST(p.price AS DOUBLE)) > 0.001"),
        ("Arithmetic", "session outcome matches its events (rule order)",
         "WITH f AS (SELECT session_id, "
         "MAX(CASE WHEN event_type='order_placed' THEN 1 ELSE 0 END) AS o, "
         "MAX(CASE WHEN event_type='ticket_created' THEN 1 ELSE 0 END) AS t, "
         "MAX(CASE WHEN event_type='add_to_cart' THEN 1 ELSE 0 END) AS a, "
         "COUNT(DISTINCT CASE WHEN event_type='product_view' THEN product_id "
         "END) AS v FROM journey_events GROUP BY session_id) "
         "SELECT COUNT(*) FROM f JOIN journey_outcomes r USING (session_id) "
         "WHERE r.outcome <> CASE WHEN o=1 THEN 'converted' "
         "WHEN t=1 THEN 'support_contact' WHEN a=1 THEN 'abandoned' "
         "WHEN v>=2 THEN 'product_switch' ELSE 'browse_only' END"),
    ]

    flags = ("SELECT session_id, "
             "MAX(CASE WHEN event_type='order_cancelled' THEN 1 ELSE 0 END) c, "
             "MAX(CASE WHEN event_type='refund_issued' THEN 1 ELSE 0 END) r, "
             "MAX(CASE WHEN event_type='payment_completed' THEN 1 ELSE 0 END) p, "
             "MAX(CASE WHEN event_type='order_placed' THEN 1 ELSE 0 END) o, "
             "MAX(CASE WHEN event_type='ticket_created' THEN 1 ELSE 0 END) t "
             "FROM journey_events GROUP BY session_id")
    checks += [
        ("Lifecycle", "order status matches cancel/refund events",
         f"WITH f AS ({flags}) SELECT COUNT(*) FROM orders o JOIN f USING "
         "(session_id) WHERE NOT ((o.status='placed' AND c=0 AND r=0) OR "
         "(o.status='cancelled' AND c=1 AND r=0) OR "
         "(o.status='refunded' AND c=1 AND r=1))"),
        ("Lifecycle", "every order has payment_completed and order_placed",
         f"WITH f AS ({flags}) SELECT COUNT(*) FROM orders o JOIN f USING "
         "(session_id) WHERE p = 0 OR o = 0"),
        ("Lifecycle", "every order_placed session has an order row",
         f"WITH f AS ({flags}) SELECT COUNT(*) FROM f WHERE o = 1 AND "
         "session_id NOT IN (SELECT session_id FROM orders)"),
        ("Lifecycle", "order_cancelled happens after order_placed",
         "SELECT COUNT(*) FROM (SELECT session_id, MIN(CASE WHEN "
         "event_type='order_placed' THEN event_time END) AS placed, "
         "MIN(CASE WHEN event_type='order_cancelled' THEN event_time END) "
         "AS cancelled FROM journey_events GROUP BY session_id) "
         "WHERE cancelled IS NOT NULL AND cancelled <= placed"),
        ("Lifecycle", "ticket rows and ticket_created events agree",
         f"WITH f AS ({flags}), n AS (SELECT session_id, COUNT(*) AS k FROM "
         "support_tickets GROUP BY session_id) SELECT COUNT(*) FROM f "
         "FULL JOIN n USING (session_id) WHERE COALESCE(f.t, 0) <> "
         "COALESCE(n.k, 0)"),
    ]

    checks += [
        ("Consent", "customer linked only when consent is granted",
         "SELECT COUNT(*) FROM sessions s JOIN customers c USING "
         "(customer_id) WHERE c.consent_status <> 'granted'"),
        ("Consent", "linked sessions are marked granted",
         "SELECT COUNT(*) FROM sessions WHERE customer_id IS NOT NULL AND "
         "consent_status <> 'granted'"),
        ("Duplicates", "no repeated event inside a session (same type, time, "
         "product), except labelled duplicate conversions",
         "SELECT COUNT(*) FROM (SELECT session_id, event_type, event_time, "
         "product_id FROM journey_events GROUP BY ALL HAVING COUNT(*) > 1)"),
        ("Separation", "ground truth never appears in input tables",
         "SELECT COUNT(*) FROM information_schema.columns WHERE "
         "table_name <> 'ground_truth' AND column_name IN ('issue_type', "
         "'issue_id', 'expected_decision', 'is_bot')"),
    ]
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="dataset folder")
    parser.add_argument("--report-dir", default="reports")
    args = parser.parse_args()
    data, report_dir = Path(args.data), Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    counts = {}
    for f in sorted(data.glob("*.csv")):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_csv("
                    f"'{f.as_posix()}', header=true, all_varchar=true)")
        counts[f.stem] = con.execute(
            f"SELECT COUNT(*) FROM {f.stem}").fetchone()[0]

    rows, failed = [], 0
    for group, name, sql in build_checks():
        bad = con.execute(sql).fetchone()[0]
        failed += bad != 0
        rows.append((group, name, bad, "PASS" if bad == 0 else "FAIL"))
        print(("PASS " if bad == 0 else "FAIL ") + f"[{group}] {name}"
              + ("" if bad == 0 else f"  ({bad} violations)"))

    lines = ["# Validation summary", "", f"Dataset folder: `{data.as_posix()}`",
             "", "## Row counts", "", "| Table | Rows |", "|---|---|"]
    lines += [f"| {t} | {n:,} |" for t, n in counts.items()]
    lines += ["", "## Checks (violations must be 0)", "",
              "| Group | Check | Violations | Result |", "|---|---|---|---|"]
    lines += [f"| {g} | {n} | {b} | {r} |" for g, n, b, r in rows]
    lines += ["", f"**{len(rows) - failed} of {len(rows)} checks passed.**", ""]
    (report_dir / "validation_summary.md").write_text("\n".join(lines),
                                                       encoding="utf-8")
    print(f"\n{len(rows) - failed} of {len(rows)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()