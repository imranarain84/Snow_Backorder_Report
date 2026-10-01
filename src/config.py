"""Environment-driven configuration. No secrets live in code."""
import os


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in your shell (local run) or as a GitHub Actions secret."
        )
    return value


class Config:
    def __init__(self):
        self.shiphero_refresh_token = _require("SHIPHERO_REFRESH_TOKEN")
        # Optional: only needed if your ShipHero credentials are for a 3PL
        # parent account acting on behalf of multiple customers. If your
        # token is already scoped to a single customer account, leave this
        # unset and every query naturally returns only that account's data.
        self.customer_account_id = os.environ.get(
            "SHIPHERO_CUSTOMER_ACCOUNT_ID", ""
        ).strip() or None
        # Optional: only set this if the report should only look at one
        # warehouse's orders. Leave unset to include orders across every
        # warehouse on the account.
        self.warehouse_id = os.environ.get(
            "SHIPHERO_WAREHOUSE_ID", ""
        ).strip() or None

        self.gmail_client_id = _require("GMAIL_CLIENT_ID")
        self.gmail_client_secret = _require("GMAIL_CLIENT_SECRET")
        self.gmail_refresh_token = _require("GMAIL_REFRESH_TOKEN")
        self.gmail_sender_email = _require("GMAIL_SENDER_EMAIL")

        recipients_raw = _require("REPORT_RECIPIENTS")
        self.recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

        self.lookback_days = int(os.environ.get("LOOKBACK_DAYS", "60"))
        self.preorder_tag = os.environ.get("PREORDER_TAG", "preorder")
        # Product families (grouped by SKU-prefix + name-base, so size/color
        # variants of the same product count together) affecting this many
        # distinct orders or more are excluded — treated as an
        # already-known, larger-scale issue rather than something this
        # report needs to surface.
        self.max_orders_per_sku = int(os.environ.get("MAX_ORDERS_PER_SKU", "5"))

        self.shiphero_auth_url = "https://public-api.shiphero.com/auth/refresh"
        self.shiphero_graphql_url = "https://public-api.shiphero.com/graphql"
