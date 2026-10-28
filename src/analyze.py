import argparse
import math
from pathlib import Path
from statistics import NormalDist

import duckdb
import pandas as pd

from journeys import HIGH_PRICE   # same cut-off the generator used

# Detection thresholds (documented in findings.md)
LATE_SECONDS = 120          # normal ingestion delay is at most 60 s
BOT_MIN_EVENTS = 40
BOT_MAX_GAP = 2             # seconds between events
BOT_MAX_STD = 0.5

STAGES = [("visit", "'page_view','app_open'"),
          ("product_view", "'product_view'"),
          ("add_to_cart", "'add_to_cart'"),
          ("checkout", "'checkout_started'"),
          ("payment", "'payment_started'"),
          ("order_placed", "'order_placed'")]


def md_table(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        out.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(out)


def pct(x):
    return f"{100 * x:.1f}%"


def prf(found, truth):
    tp = len(found & truth)
    p = tp / len(found) if found else 0.0
    r = tp / len(truth) if truth else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return tp, p, r, f


def diff_ci(x1, n1, x2, n2, z):
    p1, p2 = x1 / n1, x2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    d = p2 - p1
    return d, d - z * se, d + z * se


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--report-dir", default="reports")
    args = parser.parse_args()
    data, report_dir = Path(args.data), Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    for f in sorted(data.glob("*.csv")):
        if f.stem != "ground_truth":
            con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_csv("
                        f"'{f.as_posix()}', header=true, all_varchar=true)")
    q = lambda sql: con.execute(sql).df()

    # ----------------------------------------------------- detection ----
    late = set(q(f"""SELECT event_id FROM journey_events WHERE
        epoch(CAST(ingestion_time AS TIMESTAMP)) -
        epoch(CAST(event_time AS TIMESTAMP)) > {LATE_SECONDS}""").event_id)

    dup = set(q("""SELECT event_id FROM (SELECT event_id, ROW_NUMBER() OVER
        (PARTITION BY session_id ORDER BY CAST(event_seq AS INT)) AS n
        FROM journey_events WHERE event_type = 'order_placed')
        WHERE n > 1""").event_id)

    shared = set(q("""SELECT anonymous_id FROM sessions WHERE customer_id IS
        NOT NULL GROUP BY anonymous_id HAVING COUNT(DISTINCT customer_id) > 1
        """).anonymous_id)

    bots = set(q(f"""WITH g AS (SELECT session_id,
        epoch(CAST(event_time AS TIMESTAMP)) - LAG(epoch(CAST(event_time AS
        TIMESTAMP))) OVER (PARTITION BY session_id ORDER BY CAST(event_seq AS
        INT)) AS gap FROM journey_events)
        SELECT session_id FROM g GROUP BY session_id
        HAVING COUNT(*) >= {BOT_MIN_EVENTS} AND MAX(gap) <= {BOT_MAX_GAP}
        AND STDDEV_SAMP(gap) <= {BOT_MAX_STD}""").session_id)

    # -------- the ONLY place ground truth is read: grading the detectors
    gt = pd.read_csv(data / "ground_truth.csv", dtype=str,
                     keep_default_na=False)
    truth = {t: set(g.entity_id) for t, g in gt.groupby("issue_type")}
    merged_sessions = truth.get("wrong_identity_merge", set())
    if merged_sessions:
        ids = ", ".join(f"'{s}'" for s in merged_sessions)
        truth_anon = set(q(f"SELECT anonymous_id FROM sessions WHERE "
                           f"session_id IN ({ids})").anonymous_id)
    else:
        truth_anon = set()
    scores = []
    for name, rule, found, real in [
        ("late_event", f"ingestion delay > {LATE_SECONDS}s", late,
         truth.get("late_event", set())),
        ("duplicate_conversion", "2nd+ order_placed in a session", dup,
         truth.get("duplicate_conversion", set())),
        ("wrong_identity_merge (per anonymous_id)",
         "anonymous_id linked to 2+ customers", shared, truth_anon),
        ("bot_traffic", f">={BOT_MIN_EVENTS} events, gaps <= {BOT_MAX_GAP}s, "
         f"std <= {BOT_MAX_STD}", bots, truth.get("bot_traffic", set()))]:
        tp, p, r, f = prf(found, real)
        scores.append((name, rule, len(real), len(found), tp,
                       f"{p:.3f}", f"{r:.3f}", f"{f:.3f}"))
    score_df = pd.DataFrame(scores, columns=[
        "Problem", "Detection rule", "Labelled", "Flagged", "Correct",
        "Precision", "Recall", "F1"])

    # ------------------------------------------------------ cleaning ----
    con.register("bot_ids", pd.DataFrame({"session_id": sorted(bots)}))
    con.register("dup_ids", pd.DataFrame({"event_id": sorted(dup)}))
    con.execute("""CREATE VIEW human AS SELECT * FROM sessions WHERE
        session_id NOT IN (SELECT session_id FROM bot_ids)""")
    con.execute("""CREATE VIEW clean AS SELECT e.*,
        CAST(e.event_time AS TIMESTAMP) AS t FROM journey_events e WHERE
        e.session_id NOT IN (SELECT session_id FROM bot_ids) AND
        e.event_id NOT IN (SELECT event_id FROM dup_ids)""")
    con.execute("""CREATE VIEW reach AS SELECT session_id,
        MAX(CASE WHEN event_type IN ('page_view','app_open') THEN 1 ELSE 0 END) visit,
        MAX(CASE WHEN event_type='product_view' THEN 1 ELSE 0 END) product_view,
        MAX(CASE WHEN event_type='add_to_cart' THEN 1 ELSE 0 END) add_to_cart,
        MAX(CASE WHEN event_type='checkout_started' THEN 1 ELSE 0 END) checkout,
        MAX(CASE WHEN event_type='payment_started' THEN 1 ELSE 0 END) payment,
        MAX(CASE WHEN event_type='order_placed' THEN 1 ELSE 0 END) order_placed,
        MAX(CASE WHEN event_type='payment_failed' THEN 1 ELSE 0 END) pay_failed,
        MAX(CASE WHEN event_type='app_crash' THEN 1 ELSE 0 END) crashed
        FROM clean GROUP BY session_id""")

    n_all = q("SELECT COUNT(*) n FROM sessions").n[0]
    n_human = q("SELECT COUNT(*) n FROM human").n[0]
    raw_orders = q("SELECT COUNT(*) n FROM journey_events WHERE "
                   "event_type='order_placed'").n[0]
    real_orders = q("SELECT COUNT(*) n FROM orders").n[0]
    conv = pd.DataFrame([
        ("Raw: order_placed events / all sessions", f"{raw_orders:,}",
         f"{n_all:,}", pct(raw_orders / n_all)),
        ("Clean: sessions with an order / human sessions", f"{real_orders:,}",
         f"{n_human:,}", pct(real_orders / n_human))],
        columns=["Method", "Conversions", "Sessions", "Conversion rate"])

    # --------------------------------------------------------- funnel ----
    r = q("""SELECT COUNT(*) n, SUM(visit) a, SUM(product_view) b,
        SUM(add_to_cart) c, SUM(checkout) d, SUM(payment) e,
        SUM(order_placed) f FROM reach""").iloc[0]
    counts = [int(r.a), int(r.b), int(r.c), int(r.d), int(r.e), int(r.f)]
    funnel = []
    for i, ((name, _), c) in enumerate(zip(STAGES, counts)):
        step = "" if i == 0 else pct(c / counts[i - 1])
        funnel.append((name, f"{c:,}", pct(c / counts[0]), step,
                       "" if i == 0 else f"{counts[i - 1] - c:,}"))
    funnel_df = pd.DataFrame(funnel, columns=[
        "Stage", "Sessions", "% of visits", "Step conversion", "Lost here"])

    # ------------------------------------------------------- segments ----
    seg = q("""SELECT h.channel, h.device_type,
        COALESCE(NULLIF(h.app_version, ''), '-') AS app_version,
        COUNT(*) AS sessions,
        ROUND(100.0 * AVG(r.add_to_cart), 1) AS cart_pct,
        ROUND(100.0 * AVG(r.order_placed), 1) AS order_pct,
        ROUND(100.0 * SUM(r.order_placed) / NULLIF(SUM(r.add_to_cart), 0), 1)
          AS cart_to_order_pct,
        ROUND(100.0 * AVG(r.crashed), 1) AS crash_pct
        FROM human h JOIN reach r USING (session_id)
        GROUP BY ALL ORDER BY 1, 2, 3""")

    # ------------------------------------------------------- friction ----
    exit_df = q(f"""WITH v AS (SELECT c.session_id, c.product_id,
          ROW_NUMBER() OVER (PARTITION BY c.session_id ORDER BY
            CAST(c.event_seq AS INT) DESC) AS rn
          FROM clean c WHERE c.event_type = 'product_view'),
        x AS (SELECT v.*, p.stock_status, CAST(p.price AS DOUBLE) AS price,
          r.add_to_cart FROM v JOIN products p USING (product_id)
          JOIN reach r USING (session_id))
        SELECT CASE WHEN stock_status = 'out_of_stock' THEN 'out_of_stock'
               WHEN price > {HIGH_PRICE} THEN 'high_price (>{HIGH_PRICE})' ELSE 'normal' END
          AS product_type, COUNT(*) AS product_views,
          ROUND(100.0 * AVG(CASE WHEN rn = 1 AND add_to_cart = 0 THEN 1
            ELSE 0 END), 1) AS left_after_view_pct
        FROM x GROUP BY 1 ORDER BY 3 DESC""")

    pay = q("""SELECT CASE WHEN pay_failed = 1 THEN 'payment failed'
        ELSE 'no payment failure' END AS group_name, COUNT(*) AS sessions,
        ROUND(100.0 * AVG(order_placed), 1) AS completed_order_pct
        FROM reach WHERE payment = 1 GROUP BY 1 ORDER BY 1""")
    crash = q("""SELECT CASE WHEN r.crashed = 1 THEN 'app crash' ELSE 'no crash'
        END AS group_name, COUNT(*) AS sessions,
        ROUND(100.0 * AVG(r.order_placed), 1) AS order_pct
        FROM human h JOIN reach r USING (session_id)
        WHERE h.channel = 'app' GROUP BY 1 ORDER BY 1""")

    # ---------------------------------------------------- experiments ----
    ex_rows = []
    exps = q("SELECT experiment_id, name FROM experiments ORDER BY 1")
    n_tests = 2 * len(exps)           # two metrics per experiment
    z = NormalDist().inv_cdf(1 - 0.05 / (2 * n_tests))   # Bonferroni
    level = 100 * (1 - 0.05 / n_tests)
    for e in exps.itertuples():
        d = q(f"""SELECT se.variant, COUNT(*) AS n,
            SUM(r.add_to_cart) AS carts, SUM(r.checkout) AS checkouts,
            SUM(r.order_placed) AS orders
            FROM session_experiments se JOIN reach r USING (session_id)
            WHERE se.experiment_id = '{e.experiment_id}'
            GROUP BY 1 ORDER BY 1""").set_index("variant")
        if set(d.index) != {"A", "B"}:
            continue
        for metric, num, den in [("cart -> checkout", "checkouts", "carts"),
                                 ("checkout -> order", "orders", "checkouts")]:
            a_n, a_x = int(d.loc["A", den]), int(d.loc["A", num])
            b_n, b_x = int(d.loc["B", den]), int(d.loc["B", num])
            if min(a_n, b_n) == 0:
                continue
            diff, lo, hi = diff_ci(a_x, a_n, b_x, b_n, z)
            ex_rows.append((e.name, metric, f"{pct(a_x / a_n)} (n={a_n})",
                            f"{pct(b_x / b_n)} (n={b_n})",
                            f"{100 * diff:+.1f} pts",
                            f"[{100 * lo:+.1f}, {100 * hi:+.1f}]",
                            "yes" if lo > 0 or hi < 0 else "no"))
    ex_df = pd.DataFrame(ex_rows, columns=[
        "Experiment", "Metric", "Variant A", "Variant B", "B minus A",
        f"{level:.1f}% CI", "Clear effect?"])

    # --------------------------------------------------------- report ----
    L = ["# Findings", "",
         f"Dataset: `{data.as_posix()}`  |  sessions: {n_all:,}  |  "
         f"events: {q('SELECT COUNT(*) n FROM journey_events').n[0]:,}", "",
         "All numbers below come from the generated data. Detection and "
         "cleaning use input columns only; `ground_truth.csv` is read once, "
         "to grade the detectors.", "",
         "## 1. Can the injected problems be found?", "",
         md_table(score_df), "",
         "Late events are separable because normal ingestion delay is capped "
         f"at 60 s while injected delays start at 300 s (threshold "
         f"{LATE_SECONDS} s). The bot rule is easy by design (fixed 1-2 s "
         "gaps); a real scraper with random pauses would need more features. "
         "Merged identities are graded per anonymous_id because the data "
         "cannot say which of the two sessions on a shared id is the wrong "
         "one.", "",
         "## 2. Effect of the problems on conversion", "",
         md_table(conv), "",
         f"{len(bots):,} bot sessions and {len(dup):,} duplicate "
         "conversion events were removed to get the clean figure. Events are "
         "ordered by `event_time`, never by `ingestion_time`.", "",
         "## 3. Funnel (clean data, human sessions)", "", md_table(funnel_df),
         "", "The biggest loss is between product view and add to cart. "
         "Later stages lose fewer sessions in absolute terms.", "",
         "## 4. Drop-off by device and app version", "", md_table(seg), "",
         "## 5. Friction: where people leave", "",
         "Share of product views that were the session's last product view "
         "with no cart afterwards:", "", md_table(exit_df), "",
         "Orders completed among sessions that reached payment:", "",
         md_table(pay), "",
         "App sessions with and without a crash:", "", md_table(crash), "",
         "## 6. Experiments", "", md_table(ex_df), "",
         "Experiments overlap in time, so sessions can be in more than one. "
         f"Intervals use a normal approximation and are widened for the "
         f"{n_tests} comparisons made (Bonferroni), so a lucky result on a "
         "metric nobody changed is less likely to look real.", ""]
    (report_dir / "findings.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()