"""Injects labelled problems into the clean baseline data.

Reads the baseline folder (--src), writes the final dataset (--out) and a
separate ground_truth.csv. The baseline is never changed, so running this
twice gives the same result.

Problems injected (issue_type in ground_truth.csv):
  late_event            event arrives long after it happened
  duplicate_conversion  order_placed event recorded twice
  wrong_identity_merge  one anonymous_id shared by two customers
  bot_traffic           scraper sessions mixed in with real visitors
"""
import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from common import SEED

LATE_SESSION_RATE = 0.04    # share of sessions with one late event
DUP_RATE = 0.03             # share of converted sessions counted twice
MERGE_RATE = 0.02           # share of customer sessions with a wrong merge
BOT_RATE = 0.04             # share of all sessions that are bots
BOT_POOL = 25               # number of anonymous_ids the bots rotate through
TIME_FMT = "%Y-%m-%d %H:%M:%S"

COPY_AS_IS = ["customers", "products", "pages", "experiments", "carts",
              "cart_items", "orders", "support_tickets",
              "session_experiments"]


def read(src, name):
    return pd.read_csv(src / f"{name}.csv", dtype=str, keep_default_na=False)


def write(df, name, out):
    df.to_csv(out / f"{name}.csv", index=False, lineterminator="\n")
    print(f"{name}: {len(df)} rows")


def add_seconds(series, seconds):
    return (pd.to_datetime(series) + pd.to_timedelta(seconds, unit="s")
            ).dt.strftime(TIME_FMT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, help="baseline folder")
    parser.add_argument("--out", required=True, help="final dataset folder")
    args = parser.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng([SEED, 4])
    sessions = read(src, "sessions")
    events = read(src, "journey_events")
    outcomes = read(src, "journey_outcomes")
    products = read(src, "products")
    pages = read(src, "pages")
    n_sessions = len(sessions)
    truth = []   # (issue_type, entity_type, entity_id, related_id, detail, decision)

    # ------------------------------------------- 1. bot traffic -------
    o = outcomes.set_index("session_id")["outcome"]
    s = sessions.set_index("session_id")
    eligible = s.index[(s["customer_id"] == "")
                       & s.index.map(o).isin(["browse_only", "product_switch"])
                       ].to_numpy()
    k = int(n_sessions * BOT_RATE)
    bots = np.sort(rng.choice(eligible, k, replace=False))
    events = events[~events["session_id"].isin(bots)]

    prod_ids = products["product_id"].tolist()
    web_page = {r.page_type: r.page_id for r in pages.itertuples()
                if r.channel == "web"}
    frames = []
    for b in bots:
        n = 60 + int(rng.random() * 141)              # 60 to 200 events
        step = 1 + int(rng.random() * 2)              # exactly 1 or 2 seconds
        start = pd.Timestamp(s.at[b, "start_time"])
        first = int(rng.random() * len(prod_ids))     # crawl products in order
        times = start + pd.to_timedelta(np.arange(n) * step, unit="s")
        types = ["page_view"] + ["product_view"] * (n - 1)
        prod = [""] + [prod_ids[(first + i) % len(prod_ids)]
                       for i in range(n - 1)]
        page = [web_page["home"]] + [web_page["product"]] * (n - 1)
        frames.append(pd.DataFrame({
            "event_id": [f"EVT-{b}-{i:06d}" for i in range(1, n + 1)],
            "session_id": b, "event_seq": [str(i) for i in range(1, n + 1)],
            "event_type": types, "channel": "web", "page_id": page,
            "product_id": prod,
            "event_time": times.strftime(TIME_FMT),
            "ingestion_time": (times + pd.Timedelta(seconds=1)
                               ).strftime(TIME_FMT)}))
        pool = f"ANO-{9000000 + int(rng.random() * BOT_POOL):07d}"
        s.at[b, "channel"] = "web"
        s.at[b, "device_type"] = "desktop"
        s.at[b, "app_version"] = ""
        s.at[b, "consent_status"] = "not_logged_in"
        s.at[b, "anonymous_id"] = pool
        s.at[b, "end_time"] = times[-1].strftime(TIME_FMT)
        outcomes.loc[outcomes["session_id"] == b,
                     ["outcome", "last_stage_reached", "dropoff_stage"]] = [
            "product_switch", "product_view", "add_to_cart"]
        truth.append(("bot_traffic", "session", b, "",
                      f"{n} events, fixed {step}s gaps, products crawled in order",
                      "exclude from funnel and conversion metrics"))
    events = pd.concat([events] + frames, ignore_index=True)
    sessions = s.reset_index()[list(read(src, "sessions").columns)]

    # ------------------------------------------------ 2. late events ----
    n_ev = events.groupby("session_id").size()
    candidates = np.setdiff1d(n_ev[n_ev >= 3].index.to_numpy(), bots)  # not bots
    k = int(len(candidates) * LATE_SESSION_RATE)
    chosen = np.sort(rng.choice(candidates, k, replace=False))
    # pick one event that is not the last one, so later events can overtake it
    pick_seq = (rng.random(k) * (n_ev.loc[chosen].to_numpy() - 1)).astype(int) + 1
    delay = rng.integers(300, 7200, k)               # 5 min to 2 hours
    keys = pd.Series(np.arange(k), index=pd.Index(
        [f"EVT-{s}-{q:06d}" for s, q in zip(chosen, pick_seq)]))
    mask = events["event_id"].isin(keys.index)
    ids = events.loc[mask, "event_id"]
    d = delay[keys.loc[ids].to_numpy()]
    events.loc[mask, "ingestion_time"] = add_seconds(
        events.loc[mask, "event_time"], d)
    for eid, sec in zip(ids, d):
        truth.append(("late_event", "event", eid, "",
                      f"ingestion delayed by {sec} seconds",
                      "order by event_time, not ingestion_time"))

    # -------------------------------------- 3. duplicate conversions ----
    max_seq = events.groupby("session_id")["event_seq"].apply(
        lambda s: s.astype(int).max())
    placed = events[events["event_type"] == "order_placed"].copy()
    placed["seq"] = placed["event_seq"].astype(int)
    placed = placed[placed["seq"] == max_seq.loc[placed["session_id"]].to_numpy()]
    k = int(len(placed) * DUP_RATE)
    dup_src = placed.iloc[np.sort(rng.choice(len(placed), k, replace=False))]
    shift = rng.integers(1, 4, k)
    dups = dup_src.drop(columns="seq").copy()
    new_seq = dup_src["seq"].to_numpy() + 1
    dups["event_seq"] = new_seq.astype(str)
    dups["event_id"] = [f"EVT-{s}-{q:06d}" for s, q in
                        zip(dups["session_id"], new_seq)]
    dups["event_time"] = add_seconds(dup_src["event_time"], shift)
    dups["ingestion_time"] = add_seconds(dups["event_time"],
                                         rng.integers(1, 4, k))
    for new_id, old_id in zip(dups["event_id"], dup_src["event_id"]):
        truth.append(("duplicate_conversion", "event", new_id, old_id,
                      "order_placed recorded twice",
                      "drop the duplicate, count the conversion once"))
    events = pd.concat([events, dups], ignore_index=True)
    # the duplicate is now the session's last event, so end_time moves with it
    new_end = dict(zip(dups["session_id"], dups["event_time"]))
    sessions["end_time"] = [new_end.get(sid, end) for sid, end in
                            zip(sessions["session_id"], sessions["end_time"])]

    # ------------------------------------- 4. wrong identity merges ----
    linked = sessions.index[sessions["customer_id"] != ""].to_numpy()
    k = int(len(linked) * MERGE_RATE)
    victims = np.sort(rng.choice(linked, k, replace=False))
    original_anon = sessions["anonymous_id"].to_numpy().copy()
    cust = sessions["customer_id"].to_numpy()
    donors = np.setdiff1d(linked, victims)   # donors keep their own id
    for v in victims:
        for _ in range(20):
            donor = donors[int(rng.random() * len(donors))]
            if cust[donor] != cust[v]:
                break
        sessions.at[v, "anonymous_id"] = original_anon[donor]
        truth.append(("wrong_identity_merge", "session",
                      sessions.at[v, "session_id"],
                      sessions.at[donor, "session_id"],
                      f"anonymous_id {original_anon[v]} replaced by "
                      f"{original_anon[donor]} (belongs to {cust[donor]})",
                      "do not stitch this anonymous_id across customers"))

    # ------------------------------------------------------ write ----
    events = events.sort_values("event_id", kind="stable")
    write(events, "journey_events", out)
    write(sessions, "sessions", out)
    write(outcomes, "journey_outcomes", out)
    for name in COPY_AS_IS:
        shutil.copyfile(src / f"{name}.csv", out / f"{name}.csv")

    gt = pd.DataFrame(truth, columns=["issue_type", "entity_type", "entity_id",
                                      "related_id", "detail",
                                      "expected_decision"])
    gt.insert(0, "issue_id", [f"GT-{i:06d}" for i in range(1, len(gt) + 1)])
    write(gt, "ground_truth", out)
    print(gt["issue_type"].value_counts().to_string())


if __name__ == "__main__":
    main()