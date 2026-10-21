from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional
import json
import logging
import math
import os

import pandas as pd
from PIL import Image, ImageOps

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError, ServerError
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineConfig:
    sales_tax_rate: float = 0.0635           # Connecticut State Sales Tax Rate
    meals_tax_rate: float = 0.0735           # Connecticut Meals Tax Rate
    capitalization_threshold: float = 2500.0 # Section 179 / Fixed Asset threshold
    nec_vendor_threshold: float = 600.0      # 1099-NEC review threshold
    personal_merchants: tuple[str, ...] = ("stew leonard's", "netflix")


class CPAAutomationEngine:
    """Run accounting review checks, tax estimates, and AI shoebox document extraction."""

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self.supabase: Optional[Client] = None
        self.gemini_client = None

        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vgzymkfrtdqizytadyjf.supabase.co")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("**")

        if HAS_GENAI and GEMINI_API_KEY:
            try:
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini AI client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

        if HAS_SUPABASE and SUPABASE_URL and SUPABASE_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Supabase client: {e}")
        else:
            logger.info("Running in offline/local mode (Supabase credentials not found in environment variables).")

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

    def _call_gemini_json(self, contents: list[Any]) -> Dict[str, Any]:
        """Call Gemini Flash with automatic model fallback and strict JSON output."""
        if not self.gemini_client:
            raise RuntimeError("Gemini AI client is not initialized. Set the GEMINI_API_KEY environment variable.")

        models_to_try = ("gemini-2.5-flash", "gemini-2.0-flash")
        last_err: Optional[Exception] = None

        for model_name in models_to_try:
            for attempt in range(2):
                try:
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0,
                        ),
                    )
                    return json.loads(response.text)
                except Exception as exc:
                    last_err = exc
        raise RuntimeError(f"Gemini extraction failed: {last_err}")

    def process_shoebox_document(self, image_file_path: str) -> Dict[str, Any]:
        """
        Classifies and extracts summary data from shoebox documents (Receipts, Invoices, Bills, Bank Statements)
        using Gemini Flash, and automatically stages them into Supabase.
        """
        img = Image.open(image_file_path)
        img = ImageOps.exif_transpose(img)

        prompt = """
        Analyze this financial document image and return strict JSON with these exact keys:
        - "document_type": one of "receipt", "invoice", "bill", or "bank_statement"
        - "entity_name": Merchant, Vendor, Customer, or Bank Name printed on the document
        - "document_date": Date on the document in YYYY-MM-DD format
        - "subtotal": float
        - "tax_amount": float
        - "total_amount": float
        """

        extracted_data = self._call_gemini_json([img, prompt])
        doc_class = extracted_data.get("document_type", "receipt")
        if doc_class not in ("receipt", "invoice", "bill", "bank_statement"):
            doc_class = "receipt"

        payload = {
            "document_type": doc_class,
            "entity_name": extracted_data.get("entity_name") or "Unknown Merchant",
            "document_date": extracted_data.get("document_date") or None,
            "subtotal": round(float(extracted_data.get("subtotal") or 0.0), 2),
            "tax_amount": round(float(extracted_data.get("tax_amount") or 0.0), 2),
            "total_amount": round(float(extracted_data.get("total_amount") or 0.0), 2),
            "status": "pending",
        }

        if self.supabase:
            try:
                self.supabase.table("document_staging").insert(payload).execute()
                logger.info(f"Successfully staged [{doc_class.upper()}] document to Supabase.")
            except Exception as e:
                logger.error(f"Failed to sync document staging to Supabase: {e}")

        return payload

    def run_anomaly_scanner(self, transactions: pd.DataFrame, client_id: Optional[str] = None) -> pd.DataFrame:
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
