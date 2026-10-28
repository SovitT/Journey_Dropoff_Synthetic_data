import argparse
import bisect
import math
from pathlib import Path

import numpy as np
import pandas as pd

from common import SEED, START_DATE, END_DATE, session_id, event_id, outcome_id

# ---------------------------------------------------------------- rules ---
# Funnel stage of each event type (from design.md).
STAGE_OF = {"page_view": 1, "app_open": 1, "product_view": 2,
            "add_to_cart": 3, "checkout_started": 4,
            "payment_started": 5, "order_placed": 6}
STAGE_NAME = {0: "none", 1: "visit", 2: "product_view", 3: "add_to_cart",
              4: "checkout", 5: "payment", 6: "order_placed"}

# Which page type each event happens on (None = no page).
PAGE_OF = {"page_view": "search", "app_open": "home",
           "onboarding_view": "home", "login_completed": "login",
           "search_performed": "search", "filter_applied": "search",
           "product_view": "product", "product_image_view": "product",
           "review_viewed": "product",
           "add_to_cart": "product", "add_to_wishlist": "product",
           "checkout_started": "checkout", "payment_method_selected": "payment",
           "payment_started": "payment", "payment_failed": "payment",
           "payment_completed": "payment", "order_placed": "payment",
           "order_cancelled": "support", "refund_issued": "support",
           "app_crash": None, "faq_viewed": "faq", "quick_help_opened": "support",
           "chat_started": "support", "support_message_sent": "support",
           "ticket_created": "support", "ticket_resolved": "support"}
SUPPORT_EVENTS = {"faq_viewed", "quick_help_opened", "chat_started",
                  "support_message_sent", "ticket_created", "ticket_resolved",
                  "order_cancelled", "refund_issued"}

# Friction model (chance of leaving). These are our documented assumptions.
LEAVE_NORMAL = 0.05        # after a normal product view
LEAVE_OUT_OF_STOCK = 0.50  # product is out of stock
LEAVE_HIGH_PRICE = 0.30    # price above HIGH_PRICE
# HIGH_PRICE = 150
HIGH_PRICE = 60            # roughly the dearest 13% of products
P_BOUNCE = 0.10 
LEAVE_CART = 0.25
LEAVE_CART_BANNER = 0.18   # free_shipping_banner, variant B
LEAVE_CHECKOUT = 0.20
LEAVE_CHECKOUT_SIMPLE = 0.12  # simplified_checkout, variant B
PAYMENT_FAIL = 0.12
LEAVE_AFTER_PAY_FAIL = 0.60
LEAVE_AFTER_CRASH = 0.40
CRASH_NORMAL = 0.015
CRASH_BAD_RELEASE = 0.05   # android + app version 2.4
P_ADD_TO_CART = 0.05       # per product view of an in-stock product
P_CANCEL_ORDER = 0.03


class Dice:
    """Hands out pre-drawn random numbers so the run is fast and repeatable."""

    def __init__(self, rng, size=1_000_000):
        self.rng, self.size = rng, size
        self._refill()

    def _refill(self):
        self.buf = self.rng.random(self.size).tolist()
        self.i = 0

    def u(self):
        if self.i >= self.size:
            self._refill()
        v = self.buf[self.i]
        self.i += 1
        return v

    def chance(self, p):
        return self.u() < p

    def randint(self, n):
        return int(self.u() * n)

    def gap(self, mean, cap=900):
        # waiting time in seconds, never longer than 15 min (< 30 min rule)
        return min(cap, 1 + int(-mean * math.log(1 - self.u())))


def fmt_time(seconds):
    base = np.datetime64(START_DATE.to_datetime64(), "s")
    times = base + np.asarray(seconds, dtype="int64").astype("timedelta64[s]")
    return pd.Series(times).dt.strftime("%Y-%m-%d %H:%M:%S").to_numpy()


def save(df, name, out_dir):
    df.to_csv(out_dir / f"{name}.csv", index=False,
              lineterminator="\n", float_format="%.2f")
    print(f"{name}: {len(df)} rows")


# ----------------------------------------------------------- simulation ---
def simulate(n_sessions, rng, customers, products, pages, experiments):
    dice = Dice(rng)

    prices = products["price"].tolist()
    in_stock = (products["stock_status"] == "in_stock").tolist()
    prod_ids = products["product_id"].tolist()
    n_prod = len(prod_ids)
    # a few products are much more popular than the rest
    w = 1.0 / np.arange(1, n_prod + 1) ** 0.8
    w = w[rng.permutation(n_prod)]
    cum = np.cumsum(w / w.sum()).tolist()

    page_ids = {(r.channel, r.page_type): r.page_id for r in pages.itertuples()}
    cust_ids = customers["customer_id"].tolist()
    cust_ok = (customers["consent_status"] == "granted").tolist()
    n_cust = len(cust_ids)
    anon_pool = max(10, n_sessions // 2)

    exps = [(r.experiment_id, r.name,
             int((pd.Timestamp(r.start_date) - START_DATE).total_seconds()),
             int((pd.Timestamp(r.end_date) - START_DATE).total_seconds()) + 86400)
            for r in experiments.itertuples()]

    span = int((END_DATE - START_DATE).total_seconds())
    starts = np.sort(rng.integers(0, span, n_sessions)).tolist()

    ev_chunks, E = [], []          # events: numeric rows, flushed in chunks
    etypes, etype_code = [], {}    # event type <-> small integer
    sessions, carts, cart_items, orders = [], [], [], []
    tickets, sess_exp, outcomes = [], [], []
    n_cart = n_order = n_ticket = 0

    def code(name):
        if name not in etype_code:
            etype_code[name] = len(etypes)
            etypes.append(name)
        return etype_code[name]

    for i in range(n_sessions):
        sid_n = i + 1
        sid = session_id(sid_n)
        t = starts[i]
        t_start = t

        channel = "web" if dice.chance(0.6) else "app"
        if channel == "web":
            device = "desktop" if dice.chance(0.6) else "mobile_web"
            version = ""
        else:
            device = "ios" if dice.chance(0.45) else "android"
            version = "2.3" if dice.chance(0.5) else "2.4"
        crash_p = (CRASH_BAD_RELEASE if (device == "android" and version == "2.4")
                   else CRASH_NORMAL)

        # identity: link a customer only with consent
        cust, consent = "", "not_logged_in"
        if dice.chance(0.5):
            ci = dice.randint(n_cust)
            if cust_ok[ci]:
                cust, consent = cust_ids[ci], "granted"
                anon = f"DEV-{ci + 1:06d}-{dice.randint(2)}"   # 2 devices
            else:
                consent = "denied"
                anon = f"ANO-{dice.randint(anon_pool):07d}"
        else:
            anon = f"ANO-{dice.randint(anon_pool):07d}"

        # experiments running today; half of sessions take part
        variant = {}
        for eid, ename, es, ee in exps:
            if es <= t <= ee and dice.chance(0.5):
                variant[ename] = "A" if dice.chance(0.5) else "B"
                sess_exp.append((sid, eid, variant[ename]))

        # ---- events of this session
        ev = []   # (time, type, channel, product_index or -1)

        def emit(etype, prod=-1, gap_mean=25):
            nonlocal t
            if ev:
                t += dice.gap(gap_mean)
            ch = "support" if etype in SUPPORT_EVENTS else channel
            ev.append((t, etype, ch, prod))

        issue = None
        cart_list = []        # [product_index, quantity]
        placed = False
        left = False

        def crashed():
            nonlocal issue
            if channel == "app" and dice.chance(crash_p):
                emit("app_crash")
                issue = "app_issue"
                return dice.chance(LEAVE_AFTER_CRASH)
            return False

        emit("app_open" if channel == "app" else "page_view")
        if channel == "app" and dice.chance(0.10):
            emit("onboarding_view", gap_mean=8)
        if cust:
            emit("login_completed", gap_mean=15)

        # n_views = 1
        # while n_views < 25 and dice.chance(0.93):
        #     n_views += 1

        bounced = dice.chance(P_BOUNCE)
        n_views = 1
        while n_views < 25 and dice.chance(0.95):
            n_views += 1

        for _ in range(0 if bounced else n_views):

        # for _ in range(n_views):
            if dice.chance(0.7):
                emit("page_view")
            if dice.chance(0.4):
                emit("search_performed")
                if dice.chance(0.3):
                    emit("filter_applied")
            p = min(bisect.bisect_left(cum, dice.u()), n_prod - 1)
            emit("product_view", p, gap_mean=40)
            if dice.chance(0.6):
                emit("product_image_view", p, gap_mean=15)
            if dice.chance(0.3):
                emit("review_viewed", p, gap_mean=30)
            if channel == "web" and dice.chance(0.08):
                emit("add_to_wishlist", p)
            if crashed():
                left = True
                break
            if not in_stock[p]:
                leave_p = LEAVE_OUT_OF_STOCK
            elif prices[p] > HIGH_PRICE:
                leave_p = LEAVE_HIGH_PRICE
            else:
                leave_p = LEAVE_NORMAL
            if dice.chance(leave_p):
                left = True
                break
            if in_stock[p] and dice.chance(P_ADD_TO_CART):
                cart_list.append([p, 2 if dice.chance(0.25) else 1])
                emit("add_to_cart", p)
                break

        if cart_list and not left:
            if dice.chance(0.3):                      # maybe a second item
                for _ in range(5):
                    q = min(bisect.bisect_left(cum, dice.u()), n_prod - 1)
                    if in_stock[q] and q != cart_list[0][0]:
                        cart_list.append([q, 1])
                        emit("add_to_cart", q)
                        break
            emit("page_view")                         # cart page
            leave_p = (LEAVE_CART_BANNER
                       if variant.get("free_shipping_banner") == "B"
                       else LEAVE_CART)
            if crashed() or dice.chance(leave_p):
                left = True

        if cart_list and not left:
            emit("checkout_started", gap_mean=30)
            leave_p = (LEAVE_CHECKOUT_SIMPLE
                       if variant.get("simplified_checkout") == "B"
                       else LEAVE_CHECKOUT)
            if crashed() or dice.chance(leave_p):
                left = True

        if cart_list and not left:
            emit("payment_method_selected", gap_mean=20)
            emit("payment_started", gap_mean=15)
            if dice.chance(PAYMENT_FAIL):
                emit("payment_failed", gap_mean=5)
                issue = "payment_issue"
                if dice.chance(LEAVE_AFTER_PAY_FAIL):
                    left = True
                else:
                    emit("payment_started", gap_mean=30)   # retry
                    if dice.chance(0.05):
                        emit("payment_failed", gap_mean=5)
                        left = True
            if not left:
                emit("payment_completed", gap_mean=5)
                emit("order_placed", gap_mean=3)
                placed = True

        # ---- cart / order records (totals computed from items)
        order_id = ""
        order_status = ""
        if cart_list:
            n_cart += 1
            cart_id = f"CRT-{n_cart:06d}"
            first_cart_t = next(e[0] for e in ev if e[1] == "add_to_cart")
            carts.append((cart_id, sid, first_cart_t))
            total = 0.0
            for p, qty in cart_list:
                cart_items.append((cart_id, prod_ids[p], qty, prices[p]))
                total += qty * prices[p]
            if placed:
                n_order += 1
                order_id = f"ORD-{n_order:06d}"
                order_t = ev[-1][0]
                order_status = "placed"
                if dice.chance(P_CANCEL_ORDER):
                    emit("order_cancelled", gap_mean=120)
                    order_status = "cancelled"
                    if dice.chance(0.5):
                        emit("refund_issued", gap_mean=60)
                        order_status = "refunded"
                orders.append((order_id, sid, cart_id, cust, order_t,
                               order_status, round(total, 2)))

        # ---- support contact (at most one per session)
        if placed:
            p_sup, cat = 0.04, "order_issue"
        elif issue == "payment_issue":
            p_sup, cat = 0.30, "payment_issue"
        elif issue == "app_issue":
            p_sup, cat = 0.15, "app_issue"
        else:
            p_sup, cat = 0.015, "general"
        if dice.chance(p_sup):
            if dice.chance(0.4):
                emit("faq_viewed", gap_mean=60)
            emit("chat_started" if dice.chance(0.6) else "quick_help_opened",
                 gap_mean=40)
            for _ in range(1 + dice.randint(3)):
                emit("support_message_sent", gap_mean=45)
            if dice.chance(0.7):
                emit("ticket_created", gap_mean=30)
                n_ticket += 1
                opened = t
                resolved, status = "", "open"
                if dice.chance(0.3):                   # solved inside the chat
                    emit("ticket_resolved", gap_mean=60)
                    resolved, status = t, "resolved"
                elif dice.chance(0.85):                # solved later
                    resolved = opened + 3600 * (1 + dice.randint(72))
                    status = "resolved"
                tickets.append((f"TKT-{n_ticket:06d}", sid, cust, order_id,
                                cat, opened, resolved, status))

        # ---- outcome: first matching rule wins (design.md)
        types = {e[1] for e in ev}
        viewed = {e[3] for e in ev if e[1] == "product_view"}
        if "order_placed" in types:
            outcome = "converted"
        elif "ticket_created" in types:
            outcome = "support_contact"
        elif "add_to_cart" in types:
            outcome = "abandoned"
        elif len(viewed) >= 2:
            outcome = "product_switch"
        else:
            outcome = "browse_only"
        last_stage = max(STAGE_OF.get(e[1], 0) for e in ev)
        dropoff = ("" if outcome == "converted"
                   else STAGE_NAME[min(last_stage + 1, 6)])
        outcomes.append((outcome_id(sid), sid, outcome,
                         STAGE_NAME[last_stage], dropoff))

        sessions.append((sid, cust, anon, channel, device, version, consent,
                         t_start, ev[-1][0]))

        for seq, (et, etype, ch, p) in enumerate(ev, 1):
            ptype = PAGE_OF[etype]
            if etype in ("page_view", "app_open") and seq == 1:
                ptype = "home"
            pg = page_ids.get((channel, ptype), "") if ptype else ""
            page_n = int(pg.split("-")[1]) if pg else 0
            E.append((sid_n, seq, code(etype), 0 if ch == channel else 1,
                      1 if channel == "app" else 0, p, et, page_n))
        if len(E) > 100_000:
            ev_chunks.append(np.array(E, dtype=np.int64))
            E.clear()

    if E:
        ev_chunks.append(np.array(E, dtype=np.int64))
    return (np.vstack(ev_chunks), etypes, sessions, carts, cart_items,
            orders, tickets, sess_exp, outcomes, prod_ids)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=1000)
    parser.add_argument("--out", default="data/starter")
    args = parser.parse_args()
    out = Path(args.out)

    customers = pd.read_csv(out / "customers.csv")
    products = pd.read_csv(out / "products.csv")
    pages = pd.read_csv(out / "pages.csv")
    experiments = pd.read_csv(out / "experiments.csv")

    rng = np.random.default_rng([SEED, 2])
    (ev, etypes, sessions, carts, cart_items, orders, tickets, sess_exp,
     outcomes, prod_ids) = simulate(args.sessions, rng, customers, products,
                                    pages, experiments)

    # ---- journey_events
    sid_n, seq, tcode, is_support, is_app, prod, t, page_n = ev.T
    delay_rng = np.random.default_rng([SEED, 3])
    delay = np.minimum(delay_rng.exponential(3, len(t)), 60).astype("int64")
    et_names = np.array(etypes)[tcode]
    channel = np.where(is_support == 1, "support",
                       np.where(is_app == 1, "app", "web"))
    prod_col = np.where(prod >= 0, np.array(prod_ids)[np.clip(prod, 0, None)], "")
    page_col = np.where(page_n > 0,
                        np.char.add("PAG-", np.char.zfill(page_n.astype(str), 4)),
                        "")
    sid_str = np.char.add("SES-2026-", np.char.zfill(sid_n.astype(str), 6))
    event_ids = np.char.add(np.char.add(np.char.add("EVT-", sid_str), "-"),
                            np.char.zfill(seq.astype(str), 6))
    events = pd.DataFrame({
        "event_id": event_ids, "session_id": sid_str, "event_seq": seq,
        "event_type": et_names, "channel": channel, "page_id": page_col,
        "product_id": prod_col, "event_time": fmt_time(t),
        "ingestion_time": fmt_time(t + delay)})
    save(events, "journey_events", out)

    # ---- the other tables
    s = pd.DataFrame(sessions, columns=[
        "session_id", "customer_id", "anonymous_id", "channel", "device_type",
        "app_version", "consent_status", "start_time", "end_time"])
    s["start_time"] = fmt_time(s["start_time"])
    s["end_time"] = fmt_time(s["end_time"])
    save(s, "sessions", out)

    c = pd.DataFrame(carts, columns=["cart_id", "session_id", "created_time"])
    c["created_time"] = fmt_time(c["created_time"])
    save(c, "carts", out)

    save(pd.DataFrame(cart_items, columns=["cart_id", "product_id",
                                           "quantity", "unit_price"]),
         "cart_items", out)

    o = pd.DataFrame(orders, columns=["order_id", "session_id", "cart_id",
                                      "customer_id", "order_time", "status",
                                      "total_amount"])
    o["order_time"] = fmt_time(o["order_time"])
    save(o, "orders", out)

    tk = pd.DataFrame(tickets, columns=[
        "ticket_id", "session_id", "customer_id", "order_id", "category",
        "opened_time", "resolved_time", "status"])
    tk["opened_time"] = fmt_time(tk["opened_time"])
    done = tk["resolved_time"] != ""
    rt = np.array([""] * len(tk), dtype=object)
    if done.any():
        rt[done.to_numpy()] = fmt_time(tk.loc[done, "resolved_time"].astype("int64"))
    tk["resolved_time"] = rt
    save(tk, "support_tickets", out)

    save(pd.DataFrame(sess_exp, columns=["session_id", "experiment_id",
                                         "variant"]),
         "session_experiments", out)
    save(pd.DataFrame(outcomes, columns=[
        "outcome_id", "session_id", "outcome", "last_stage_reached",
        "dropoff_stage"]), "journey_outcomes", out)


if __name__ == "__main__":
    main()