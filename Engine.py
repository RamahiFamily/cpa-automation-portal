from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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
    HAS_GENAI = True
except ImportError:
    genai = None
    types = None
    HAS_GENAI = False

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    create_client = None
    Client = Any
    HAS_SUPABASE = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineConfig:
    sales_tax_rate: float = 0.0635
    meals_tax_rate: float = 0.0735
    luxury_tax_rate: float = 0.0775
    vehicle_rental_tax_rate: float = 0.0935
    capitalization_threshold: float = 2500.0
    nec_vendor_threshold: float = 600.0
    personal_merchants: tuple[str, ...] = ("stew leonard's", "netflix")


class CPAAutomationEngine:
    """Accounting review, CT tax estimates, and document extraction.

    Keep service-role credentials and AI keys on the server. The browser should
    use only a Supabase anon/publishable key protected by RLS.
    """

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self.supabase: Optional[Client] = None
        self.gemini_client = None

        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        supabase_url = os.getenv("SUPABASE_URL", "").strip()
        supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or ""
        ).strip()

        if HAS_GENAI and gemini_key:
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
                logger.info("Gemini client initialized.")
            except Exception:
                logger.exception("Gemini initialization failed.")

        if HAS_SUPABASE and supabase_url and supabase_key:
            try:
                self.supabase = create_client(supabase_url, supabase_key)
                logger.info("Supabase client initialized.")
            except Exception:
                logger.exception("Supabase initialization failed.")
        else:
            logger.warning("Supabase is not configured; running locally.")

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

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            number = float(value or 0)
            return number if math.isfinite(number) else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _call_gemini_json(self, contents: list[Any]) -> Dict[str, Any]:
        if not self.gemini_client:
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY on the server.")

        last_error: Optional[Exception] = None
        for model_name in ("gemini-2.5-flash", "gemini-2.0-flash"):
            for _ in range(2):
                try:
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0,
                        ),
                    )
                    text = (response.text or "{}").strip()
                    data = json.loads(text)
                    if not isinstance(data, dict):
                        raise ValueError("Gemini response was not a JSON object")
                    return data
                except Exception as exc:
                    last_error = exc
                    logger.warning("Gemini call failed for %s: %s", model_name, exc)
        raise RuntimeError(f"Gemini extraction failed: {last_error}")

    def process_shoebox_document(
        self,
        image_file_path: str,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        with Image.open(image_file_path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")

        prompt = """
Return one strict JSON object with exactly these keys:
- document_type: receipt, invoice, bill, or bank_statement
- entity_name: merchant, vendor, customer, or bank
- document_date: YYYY-MM-DD or null
- subtotal: non-negative number
- tax_amount: non-negative number
- total_amount: non-negative number
Do not invent unreadable values. Use 0 for unreadable monetary fields.
"""
        extracted = self._call_gemini_json([image, prompt])
        document_type = str(extracted.get("document_type") or "receipt").lower()
        if document_type not in {"receipt", "invoice", "bill", "bank_statement"}:
            document_type = "receipt"

        subtotal = self._safe_float(extracted.get("subtotal"))
        tax_amount = self._safe_float(extracted.get("tax_amount"))
        total_amount = self._safe_float(extracted.get("total_amount"))
        if total_amount == 0 and subtotal + tax_amount > 0:
            total_amount = subtotal + tax_amount

        payload: Dict[str, Any] = {
            "document_type": document_type,
            "entity_name": str(extracted.get("entity_name") or "Unknown Merchant").strip(),
            "document_date": extracted.get("document_date") or None,
            "subtotal": round(subtotal, 2),
            "tax_amount": round(tax_amount, 2),
            "total_amount": round(total_amount, 2),
            "status": "pending",
            "source_system": "ai_shoebox",
        }
        if client_id:
            payload["client_id"] = client_id

        if self.supabase:
            response = self.supabase.table("document_staging").insert(payload).execute()
            if getattr(response, "data", None) is None:
                raise RuntimeError("Supabase insert returned no data")
        return payload

    def run_anomaly_scanner(
        self,
        transactions: pd.DataFrame,
        client_id: Optional[str] = None,
    ) -> pd.DataFrame:
        if not isinstance(transactions, pd.DataFrame):
            raise TypeError("transactions must be a pandas DataFrame")
        self._require_columns(transactions, ("date", "vendor", "amount", "category"))

        df = transactions.copy()
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        if df["amount"].isna().any():
            raise ValueError("All transaction amounts must be numeric")

        defaults = {
            "business_purpose": "",
            "is_fixed_asset": False,
            "is_1099_vendor": False,
            "w9_on_file": False,
        }
        for column, default in defaults.items():
            if column not in df.columns:
                df[column] = default

        personal = {merchant.casefold() for merchant in self.config.personal_merchants}
        findings: list[Dict[str, Any]] = []
        for index, row in df.iterrows():
            vendor = str(row["vendor"]).strip()
            amount = float(row["amount"])
            flags: list[str] = []
            if vendor.casefold() in personal and not str(row["business_purpose"]).strip():
                flags.append("Possible commingled personal expense")
            if bool(row["is_fixed_asset"]) and amount > self.config.capitalization_threshold:
                flags.append("Fixed asset over capitalization threshold")
            if (
                bool(row["is_1099_vendor"])
                and amount >= self.config.nec_vendor_threshold
                and not bool(row["w9_on_file"])
            ):
                flags.append("Missing W-9 for vendor at or over review threshold")

            for flag in flags:
                finding: Dict[str, Any] = {
                    "source_index": str(index),
                    "date": str(row["date"]),
                    "vendor": vendor,
                    "amount": round(amount, 2),
                    "flag": flag,
                }
                if client_id:
                    finding["client_id"] = client_id
                findings.append(finding)

        columns = ["source_index", "date", "vendor", "amount", "flag", "client_id"]
        result = pd.DataFrame(findings)
        if result.empty:
            result = pd.DataFrame(columns=columns)

        if findings and client_id and self.supabase:
            self.supabase.table("audit_flags").upsert(findings).execute()
        return result

    def calculate_ct_os114(
        self,
        gross_retail: float,
        gross_meals: float,
        business_use_taxable_purchases: float = 0.0,
        gross_luxury: float = 0.0,
        gross_vehicle_rental: float = 0.0,
        deductions: float = 0.0,
    ) -> Dict[str, Any]:
        values = {
            "gross_retail": self._money(gross_retail, "gross_retail"),
            "gross_meals": self._money(gross_meals, "gross_meals"),
            "business_use_taxable_purchases": self._money(
                business_use_taxable_purchases,
                "business_use_taxable_purchases",
            ),
            "gross_luxury": self._money(gross_luxury, "gross_luxury"),
            "gross_vehicle_rental": self._money(
                gross_vehicle_rental,
                "gross_vehicle_rental",
            ),
            "deductions": self._money(deductions, "deductions"),
        }
        taxable_retail = max(0.0, values["gross_retail"] - values["deductions"])
        taxes = {
            "general_sales_tax": round(taxable_retail * self.config.sales_tax_rate, 2),
            "meals_tax": round(values["gross_meals"] * self.config.meals_tax_rate, 2),
            "luxury_tax": round(values["gross_luxury"] * self.config.luxury_tax_rate, 2),
            "vehicle_rental_tax": round(
                values["gross_vehicle_rental"] * self.config.vehicle_rental_tax_rate,
                2,
            ),
            "business_use_tax": round(
                values["business_use_taxable_purchases"] * self.config.sales_tax_rate,
                2,
            ),
        }
        taxes["total"] = round(sum(taxes.values()), 2)
        return {"inputs": values, "tax": taxes, "calculated_on": date.today().isoformat()}

    def generate_trial_balance(
        self,
        ledger: pd.DataFrame,
        irs_line_map: Optional[Mapping[str, str]] = None,
    ) -> pd.DataFrame:
        if not isinstance(ledger, pd.DataFrame):
            raise TypeError("ledger must be a pandas DataFrame")
        self._require_columns(ledger, ("account", "category", "debit", "credit"))

        df = ledger.copy()
        for column in ("debit", "credit"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
            if df[column].isna().any():
                raise ValueError(f"All {column} values must be numeric")

        grouped = df.groupby(["account", "category"], as_index=False)[["debit", "credit"]].sum()
        grouped["balance"] = grouped["debit"] - grouped["credit"]
        grouped["irs_form_line"] = grouped["category"].map(dict(irs_line_map or {})).fillna(
            "Unmapped - review required"
        )
        return grouped[["account", "category", "debit", "credit", "balance", "irs_form_line"]]
