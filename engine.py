"""Financial processing engine for a CPA automation portal.

Provides review-oriented automation with hardened error handling, safe index parsing,
and optional Supabase synchronization.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional
import logging
import math
import os

import pandas as pd
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURATION & CREDENTIALS BLOCK
# (All hardcoded endpoints, keys, and default business rules are defined here)
# ==============================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://vgzymkfrtdqizytadyjf.supabase.co/rest/v1/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZnenlta2ZydGRxaXp5dGFkeWpmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MjE0NDY5NSwiZXhwIjoyMTA3NzIwNjk1fQ.Il0Zh9j1JePWFk_VOubRQOdPTvdu8ivAzZSLHfEqglE")

@dataclass(frozen=True)
class EngineConfig:
    sales_tax_rate: float = 0.0635          # Connecticut State Sales Tax Rate
    meals_tax_rate: float = 0.0735          # Connecticut Meals Tax Rate
    capitalization_threshold: float = 2500.0 # Section 179 / Fixed Asset threshold
    nec_vendor_threshold: float = 600.0     # 1099-NEC review threshold
    personal_merchants: tuple[str, ...] = ("stew leonard's", "netflix")
# ==============================================================================


class CPAAutomationEngine:
    """Run accounting review checks and generate tax/accounting summaries."""

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self.supabase: Optional[Client] = None
        
        # Safely initialize Supabase using the top-level configuration
        if HAS_SUPABASE and SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and "YOUR_" not in SUPABASE_URL:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Supabase client: {e}")
        else:
            logger.info("Running in offline/local mode (Supabase sync disabled).")

    @staticmethod
    def _require_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

    @staticmethod
    def _money(value: Any, field: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric") from exc
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{field} must be a finite non-negative number")
        return number

    def run_anomaly_scanner(self, transactions: pd.DataFrame, client_id: Optional[str] = None) -> pd.DataFrame:
        """Return flagged transaction-level exceptions and optionally push to Supabase."""
        if not isinstance(transactions, pd.DataFrame):
            raise TypeError("transactions must be a pandas DataFrame")
        self._require_columns(transactions, ("date", "vendor", "amount", "category"))

        df = transactions.copy()
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        if df["amount"].isna().any():
            raise ValueError("All transaction amounts must be numeric")

        for col, default in {
            "business_purpose": "",
            "is_fixed_asset": False,
            "is_1099_vendor": False,
            "w9_on_file": False,
        }.items():
            if col not in df.columns:
                df[col] = default

        personal = {m.lower() for m in self.config.personal_merchants}
        findings = []
        for idx, row in df.iterrows():
            vendor = str(row["vendor"]).strip()
            amount = float(row["amount"])
            flags = []

            if vendor.lower() in personal and not str(row["business_purpose"]).strip():
                flags.append("Possible commingled personal expense")
            if bool(row["is_fixed_asset"]) and amount > self.config.capitalization_threshold:
                flags.append("Fixed asset over capitalization threshold: review Section 179 eligibility")
            if bool(row["is_1099_vendor"]) and amount >= self.config.nec_vendor_threshold and not bool(row["w9_on_file"]):
                flags.append("Missing W-9 for vendor at/over configured 1099-NEC review threshold")

            # Safely handle non-integer DataFrame indices
            source_idx = int(idx) if isinstance(idx, (int, pd.Int64Dtype)) else str(idx)

            for flag in flags:
                finding = {
                    "source_index": source_idx,
                    "date": str(row["date"]),
                    "vendor": vendor,
                    "amount": amount,
                    "flag": flag,
                }
                if client_id:
                    finding["client_id"] = client_id
                findings.append(finding)

        results_df = pd.DataFrame(findings, columns=["source_index", "date", "vendor", "amount", "flag"])

        # Push findings to Supabase if connected
        if findings and client_id and self.supabase:
            try:
                self.supabase.table("audit_flags").upsert(findings).execute()
                logger.info(f"Successfully synced {len(findings)} audit flags to Supabase.")
            except Exception as e:
                logger.error(f"Failed to push audit flags to Supabase: {e}")

        return results_df

    def calculate_ct_os114(
        self,
        gross_retail: float,
        gross_meals: float,
        business_use_taxable_purchases: float = 0.0,
        business_use_tax_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculate configurable CT sales, meals, and business-use tax estimates."""
        retail = self._money(gross_retail, "gross_retail")
        meals = self._money(gross_meals, "gross_meals")
        use_base = self._money(business_use_taxable_purchases, "business_use_taxable_purchases")
        use_rate = self.config.sales_tax_rate if business_use_tax_rate is None else self._money(business_use_tax_rate, "business_use_tax_rate")
        if use_rate > 1:
            raise ValueError("business_use_tax_rate must be a decimal rate, such as 0.0635")

        sales_tax = round(retail * self.config.sales_tax_rate, 2)
        meals_tax = round(meals * self.config.meals_tax_rate, 2)
        use_tax = round(use_base * use_rate, 2)
        
        return {
            "inputs": {"gross_retail": retail, "gross_meals": meals, "business_use_taxable_purchases": use_base},
            "rates": {"sales_tax": self.config.sales_tax_rate, "meals_tax": self.config.meals_tax_rate, "business_use_tax": use_rate},
            "tax": {"sales_tax": sales_tax, "meals_tax": meals_tax, "business_use_tax": use_tax, "total": round(sales_tax + meals_tax + use_tax, 2)},
        }

    def generate_trial_balance(
        self,
        ledger: pd.DataFrame,
        irs_line_map: Optional[Mapping[str, str]] = None,
    ) -> pd.DataFrame:
        """Aggregate ledger balances by account/category and map them to supplied IRS lines."""
        if not isinstance(ledger, pd.DataFrame):
            raise TypeError("ledger must be a pandas DataFrame")
        self._require_columns(ledger, ("account", "category", "debit", "credit"))
        df = ledger.copy()
        for col in ("debit", "credit"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if df[col].isna().any():
                raise ValueError(f"All {col} values must be numeric")

        grouped = df.groupby(["account", "category"], as_index=False)[["debit", "credit"]].sum()
        grouped["balance"] = grouped["debit"] - grouped["credit"]
        mapping = dict(irs_line_map or {})
        grouped["irs_form_line"] = grouped["category"].map(mapping).fillna("Unmapped - review required")
        return grouped[["account", "category", "debit", "credit", "balance", "irs_form_line"]]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = CPAAutomationEngine()
    sample = pd.DataFrame([
        {"date": "2026-10-01", "vendor": "Netflix", "amount": 25.0, "category": "Subscriptions", "business_purpose": ""},
        {"date": "2026-10-02", "vendor": "Equipment Co", "amount": 3200.0, "category": "Equipment", "is_fixed_asset": True},
    ])
    print(engine.run_anomaly_scanner(sample).to_string(index=False))
    print(engine.calculate_ct_os114(10_000, 5_000))
