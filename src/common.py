import pandas as pd

SEED = 20261022
START_DATE = pd.Timestamp("2026-01-01")
END_DATE = pd.Timestamp("2026-03-31 23:59:59")
SESSION_GAP_MINUTES = 30


def customer_id(n):
    return f"CUS-{n:06d}"


def product_id(n):
    return f"PRD-{n:04d}"


def page_id(n):
    return f"PAG-{n:04d}"


def session_id(n):
    return f"SES-2026-{n:06d}"


def event_id(session, n):
    return f"EVT-{session}-{n:06d}"


def experiment_id(n):
    return f"EXP-2026-{n:06d}"


def outcome_id(session):
    return f"OUT-{session}"