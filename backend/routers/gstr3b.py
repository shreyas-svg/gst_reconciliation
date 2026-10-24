"""
GSTR-3B Router
==============
Provides:
  GET /gstr3b/summary  — GSTR-3B period summary (existing, DB-backed)
  GET /gstr3b/cross-form — Cross-form comparison between GSTR-1/2A and GSTR-3B

Cross-form analysis compares compatible aggregated figures only:
  - GSTR-1 outward-supply total (Sales Register + GSTR-1 reconciled tax) vs
    GSTR-3B Table 3.1 output tax
  - GSTR-2A ITC total vs GSTR-3B Table 4(A) eligible ITC

Differences are reported as investigation recommendations, NOT as confirmed errors.
GSTR-2B is not yet available in the dataset; its absence is documented explicitly.
"""

from pathlib import Path
from typing import Optional
import calendar
import re
from datetime import date as dt_date

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.models import Business, Gstr3bSummary, Invoice
from services.auth import get_current_business

router = APIRouter(prefix="/gstr3b", tags=["GSTR-3B"])

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _validate_tax_period(tax_period: Optional[str]):
    """Validate tax_period is in YYYY-MM format with month between 01 and 12."""
    if not tax_period:
        return None, None, None
    period_str = tax_period.strip()
    match = re.match(r"^(\d{4})-(0[1-9]|1[0-2])$", period_str)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tax_period format. Expected YYYY-MM with month between 01 and 12 (e.g., 2026-07).",
        )
    year = int(match.group(1))
    month = int(match.group(2))
    _, last_day = calendar.monthrange(year, month)
    return period_str, dt_date(year, month, 1), dt_date(year, month, last_day)


def _load_gstr3b_row(tax_period: Optional[str]):
    """Load GSTR-3B CSV summary for the given period, or the first available row."""
    try:
        df = pd.read_csv(DATA / "gstr3b.csv")
        if df.empty:
            return None, None
        if tax_period:
            match = df[df["tax_period"].astype(str) == tax_period.strip()]
            if not match.empty:
                return match.iloc[0], tax_period.strip()
        row = df.iloc[0]
        return row, str(row["tax_period"])
    except Exception:
        return None, None


def _get_db_invoice_sums(business_id: int, db: Session, start_date=None, end_date=None):
    """
    Sum taxable_value and gst_amount by source type for the given business.
    Returns dict: source -> {taxable_value: float, gst_amount: float, count: int}
    """
    query = select(Invoice).where(Invoice.business_id == business_id)
    if start_date and end_date:
        query = query.where(
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date,
        )
    invoices = db.scalars(query).all()

    sums: dict = {}
    for inv in invoices:
        src = inv.source
        if src not in sums:
            sums[src] = {"taxable_value": 0.0, "gst_amount": 0.0, "count": 0}
        sums[src]["taxable_value"] += inv.taxable_value or 0
        sums[src]["gst_amount"] += inv.gst_amount or 0
        sums[src]["count"] += 1
    return sums


@router.get("/summary")
def gstr3b_summary(
    tax_period: Optional[str] = Query(None, description="Optional tax period filter YYYY-MM"),
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    """
    Returns GSTR-3B summary figures for the given tax period.
    Checks database-persisted tenant summary records first.
    For multi-business setups, only business_id == 1 has sample CSV data fallback;
    others return zeros to prevent fabricating values for tenants with no GSTR-3B filing.
    """
    resolved_period_str, _, _ = _validate_tax_period(tax_period)
    target_period = resolved_period_str or (tax_period.strip() if tax_period else None)

    # 1. Check database for business-specific GSTR-3B summary records
    db_summary = None
    if target_period:
        db_summary = db.scalar(
            select(Gstr3bSummary).where(
                Gstr3bSummary.business_id == current_business.id,
                Gstr3bSummary.tax_period == target_period,
            )
        )
    else:
        db_summary = db.scalar(
            select(Gstr3bSummary)
            .where(Gstr3bSummary.business_id == current_business.id)
            .order_by(Gstr3bSummary.tax_period.desc(), Gstr3bSummary.id.desc())
        )

    if db_summary:
        return {
            "business_id": current_business.id,
            "tax_period": db_summary.tax_period,
            "output_tax": float(db_summary.output_tax),
            "eligible_itc": float(db_summary.eligible_itc),
            "itc_reversed": float(db_summary.itc_reversed),
            "net_itc": float(db_summary.net_itc),
            "data_available": True,
        }

    # 2. Fall back to sample CSV file for demo business (id == 1)
    row, period = _load_gstr3b_row(resolved_period_str or tax_period)
    resolved_period = resolved_period_str or period or (tax_period.strip() if tax_period else "2026-07")

    if row is None or current_business.id != 1:
        # Do not fabricate values for businesses without GSTR-3B data
        return {
            "business_id": current_business.id,
            "tax_period": resolved_period,
            "output_tax": 0.0,
            "eligible_itc": 0.0,
            "itc_reversed": 0.0,
            "net_itc": 0.0,
            "data_available": False,
            "note": "No GSTR-3B filing data available for this business. Upload GSTR-3B CSV to enable analysis.",
        }

    return {
        "business_id": current_business.id,
        "tax_period": resolved_period,
        "output_tax": float(row["output_tax"]),
        "eligible_itc": float(row["eligible_itc"]),
        "itc_reversed": float(row["itc_reversed"]),
        "net_itc": float(row["net_itc"]),
        "data_available": True,
    }


@router.get("/cross-form")
def gstr3b_cross_form(
    tax_period: Optional[str] = Query(None, description="Optional tax period filter YYYY-MM"),
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    """
    Cross-form comparison between detailed register data and GSTR-3B summary.

    Compares:
    1. Sales Register vs GSTR-1 filed outward supplies vs GSTR-3B Table 3.1 output tax
    2. Purchase Register vs GSTR-2A and GSTR-2B auto-drafted inward supplies
    3. GSTR-2A/2B inward ITC vs GSTR-3B Table 4(A) eligible ITC claimed
    4. Identifies tax-period inconsistencies and missing data

    Returns investigation recommendations — NOT confirmed compliance errors.
    """
    period_str, start_date, end_date = _validate_tax_period(tax_period)

    # Check database Gstr3bSummary first
    db_summary = None
    if period_str:
        db_summary = db.scalar(
            select(Gstr3bSummary).where(
                Gstr3bSummary.business_id == current_business.id,
                Gstr3bSummary.tax_period == period_str,
            )
        )
    else:
        db_summary = db.scalar(
            select(Gstr3bSummary)
            .where(Gstr3bSummary.business_id == current_business.id)
            .order_by(Gstr3bSummary.tax_period.desc(), Gstr3bSummary.id.desc())
        )

    # Load GSTR-3B CSV row as fallback
    gstr3b_row, csv_period = _load_gstr3b_row(period_str)
    resolved_period = period_str or (db_summary.tax_period if db_summary else None) or csv_period or "2026-07"

    # Load DB invoice sums for this business
    try:
        db_sums = _get_db_invoice_sums(current_business.id, db, start_date, end_date)
    except Exception:
        db_sums = {}

    sales_reg_gst = db_sums.get("sales_register", {}).get("gst_amount", 0.0)
    gstr1_gst = db_sums.get("gstr1", {}).get("gst_amount", 0.0)
    purchase_reg_gst = db_sums.get("purchase_register", {}).get("gst_amount", 0.0)
    gstr2a_gst = db_sums.get("gstr2a", {}).get("gst_amount", 0.0)
    gstr2b_gst = db_sums.get("gstr2b", {}).get("gst_amount", 0.0)

    sales_reg_tv = db_sums.get("sales_register", {}).get("taxable_value", 0.0)
    gstr1_tv = db_sums.get("gstr1", {}).get("taxable_value", 0.0)
    purchase_reg_tv = db_sums.get("purchase_register", {}).get("taxable_value", 0.0)
    gstr2a_tv = db_sums.get("gstr2a", {}).get("taxable_value", 0.0)
    gstr2b_tv = db_sums.get("gstr2b", {}).get("taxable_value", 0.0)

    has_gstr2b = db_sums.get("gstr2b", {}).get("count", 0) > 0
    has_gstr2a = db_sums.get("gstr2a", {}).get("count", 0) > 0
    has_db_data = bool(db_sums)

    # GSTR-3B declared values
    if db_summary:
        gstr3b_available = True
        gstr3b_output_tax = float(db_summary.output_tax)
        gstr3b_eligible_itc = float(db_summary.eligible_itc)
        gstr3b_itc_reversed = float(db_summary.itc_reversed)
        gstr3b_net_itc = float(db_summary.net_itc)
    elif gstr3b_row is not None and current_business.id == 1:
        gstr3b_available = True
        gstr3b_output_tax = float(gstr3b_row["output_tax"])
        gstr3b_eligible_itc = float(gstr3b_row["eligible_itc"])
        gstr3b_itc_reversed = float(gstr3b_row["itc_reversed"])
        gstr3b_net_itc = float(gstr3b_row["net_itc"])
    else:
        gstr3b_available = False
        gstr3b_output_tax = gstr3b_eligible_itc = gstr3b_itc_reversed = gstr3b_net_itc = 0.0

    # ── Cross-form comparison 1: Output tax liability ──
    # GSTR-1 total (filed outward supplies) vs GSTR-3B Table 3.1
    gstr1_to_gstr3b_diff = round(gstr1_gst - gstr3b_output_tax, 2)
    # Sales register vs GSTR-1 (outward supply agreement)
    sales_to_gstr1_diff = round(sales_reg_gst - gstr1_gst, 2)

    # ── Cross-form comparison 2: Input tax credit ──
    # GSTR-2A vs GSTR-3B Table 4(A)
    gstr2a_to_gstr3b_diff = round(gstr2a_gst - gstr3b_eligible_itc, 2)
    # GSTR-2B vs GSTR-3B Table 4(A)
    gstr2b_to_gstr3b_diff = round(gstr2b_gst - gstr3b_eligible_itc, 2) if has_gstr2b else None
    # Purchase register vs GSTR-2A
    purchase_to_gstr2a_diff = round(purchase_reg_gst - gstr2a_gst, 2)
    # Purchase register vs GSTR-2B
    purchase_to_gstr2b_diff = round(purchase_reg_gst - gstr2b_gst, 2) if has_gstr2b else None
    # GSTR-2A vs GSTR-2B (timing difference between dynamic 2A and static 2B)
    gstr2a_to_gstr2b_diff = round(gstr2a_gst - gstr2b_gst, 2) if (has_gstr2a and has_gstr2b) else None

    # Indicative net tax calculation
    estimated_net_tax = round(max(0.0, gstr3b_output_tax - gstr3b_net_itc), 2)

    # Build findings list
    findings = []

    if not has_db_data:
        findings.append({
            "finding_id": "cf-no-data",
            "category": "DATA_AVAILABILITY",
            "severity": "INFO",
            "description": "No invoice records found in the database for this business and period.",
            "recommendation": "Upload Sales Register, GSTR-1, Purchase Register, and GSTR-2A/2B CSV files to enable cross-form analysis.",
        })
    else:
        if not gstr3b_available:
            findings.append({
                "finding_id": "cf-no-gstr3b",
                "category": "DATA_AVAILABILITY",
                "severity": "INFO",
                "description": "GSTR-3B summary data is not available for this business. Cross-form comparison against Table 3.1 and Table 4(A) cannot be performed.",
                "recommendation": "Add GSTR-3B data to enable full cross-form analysis.",
            })

        # Sales register vs GSTR-1
        if abs(sales_to_gstr1_diff) > 0.01:
            sev = "HIGH" if abs(sales_to_gstr1_diff) > 5000 else "MEDIUM"
            findings.append({
                "finding_id": "cf-sales-gstr1-diff",
                "category": "OUTWARD_SUPPLY_DISCREPANCY",
                "severity": sev,
                "register_value": round(sales_reg_gst, 2),
                "gst_portal_value": round(gstr1_gst, 2),
                "difference": sales_to_gstr1_diff,
                "description": (
                    f"Sales Register GST total (₹{sales_reg_gst:,.2f}) differs from "
                    f"GSTR-1 filed GST total (₹{gstr1_gst:,.2f}) by ₹{abs(sales_to_gstr1_diff):,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: Invoices present in books but not yet filed in GSTR-1.",
                    "Hypothesis: Invoices filed in GSTR-1 but not recorded in sales register.",
                    "Hypothesis: Amendments or credit notes not reflected in one source.",
                    "Hypothesis: Tax-period differences — some invoices may belong to a different period.",
                ],
                "recommendation": "Run the Sales Reconciliation report to identify specific mismatches. Investigate before filing GSTR-3B.",
            })

        # GSTR-1 vs GSTR-3B Table 3.1
        if gstr3b_available and abs(gstr1_to_gstr3b_diff) > 0.01:
            sev = "HIGH" if abs(gstr1_to_gstr3b_diff) > 5000 else "MEDIUM"
            findings.append({
                "finding_id": "cf-gstr1-gstr3b-diff",
                "category": "GSTR1_VS_GSTR3B_OUTPUT_TAX",
                "severity": sev,
                "register_value": round(gstr1_gst, 2),
                "gst_portal_value": gstr3b_output_tax,
                "difference": gstr1_to_gstr3b_diff,
                "description": (
                    f"GSTR-1 filed output tax (₹{gstr1_gst:,.2f}) differs from "
                    f"GSTR-3B Table 3.1 declared output tax (₹{gstr3b_output_tax:,.2f}) "
                    f"by ₹{abs(gstr1_to_gstr3b_diff):,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: GSTR-3B filed before all GSTR-1 amendments were processed.",
                    "Hypothesis: B2C or export supplies included differently between forms.",
                    "Hypothesis: Amendments (GSTR-1A) not reflected in GSTR-3B.",
                ],
                "recommendation": (
                    "Verify GSTR-3B Table 3.1 matches the sum of all taxable outward "
                    "supplies from GSTR-1. File an amendment return if a material "
                    "difference exists. Consult your GST practitioner."
                ),
            })

        # Purchase register vs GSTR-2A
        if has_gstr2a and abs(purchase_to_gstr2a_diff) > 0.01:
            sev = "HIGH" if abs(purchase_to_gstr2a_diff) > 5000 else "MEDIUM"
            findings.append({
                "finding_id": "cf-purchase-gstr2a-diff",
                "category": "ITC_AVAILABILITY_DISCREPANCY",
                "severity": sev,
                "register_value": round(purchase_reg_gst, 2),
                "gst_portal_value": round(gstr2a_gst, 2),
                "difference": purchase_to_gstr2a_diff,
                "description": (
                    f"Purchase Register ITC total (₹{purchase_reg_gst:,.2f}) differs from "
                    f"GSTR-2A supplier-filed ITC (₹{gstr2a_gst:,.2f}) by "
                    f"₹{abs(purchase_to_gstr2a_diff):,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: Supplier has not filed GSTR-1 for some invoices.",
                    "Hypothesis: Purchase recorded in a different tax period than supplier filing.",
                    "Hypothesis: Invoice amendments or credit notes not yet reflected.",
                ],
                "recommendation": (
                    "Only claim ITC for invoices confirmed in GSTR-2A/2B. Contact suppliers "
                    "for unfiled invoices. Note: Missing invoices require vendor follow-up rather than automatic assumption of ineligibility."
                ),
            })

        # Purchase register vs GSTR-2B (when GSTR-2B present)
        if has_gstr2b and purchase_to_gstr2b_diff is not None and abs(purchase_to_gstr2b_diff) > 0.01:
            sev = "HIGH" if abs(purchase_to_gstr2b_diff) > 5000 else "MEDIUM"
            findings.append({
                "finding_id": "cf-purchase-gstr2b-diff",
                "category": "GSTR2B_ITC_ELIGIBILITY_DISCREPANCY",
                "severity": sev,
                "register_value": round(purchase_reg_gst, 2),
                "gst_portal_value": round(gstr2b_gst, 2),
                "difference": purchase_to_gstr2b_diff,
                "description": (
                    f"Purchase Register ITC total (₹{purchase_reg_gst:,.2f}) differs from "
                    f"GSTR-2B auto-drafted ITC statement (₹{gstr2b_gst:,.2f}) by "
                    f"₹{abs(purchase_to_gstr2b_diff):,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: Supplier filed GSTR-1 after the 11th/13th cut-off date (will appear in next month's GSTR-2B).",
                    "Hypothesis: Invoice booked internally in this period belongs to a different return period.",
                    "Hypothesis: Supplier omitted invoice from GSTR-1.",
                ],
                "recommendation": (
                    "Under Rule 36(4), ITC claim in GSTR-3B should be aligned with GSTR-2B. "
                    "Investigate invoices missing from GSTR-2B to verify if supplier filed late."
                ),
            })

        # GSTR-2A vs GSTR-2B comparison (cut-off timing variance)
        if has_gstr2a and has_gstr2b and gstr2a_to_gstr2b_diff is not None and abs(gstr2a_to_gstr2b_diff) > 0.01:
            findings.append({
                "finding_id": "cf-gstr2a-vs-gstr2b",
                "category": "GSTR2A_VS_GSTR2B_TIMING_VARIANCE",
                "severity": "INFO",
                "register_value": round(gstr2a_gst, 2),
                "gst_portal_value": round(gstr2b_gst, 2),
                "difference": gstr2a_to_gstr2b_diff,
                "description": (
                    f"Dynamic GSTR-2A (₹{gstr2a_gst:,.2f}) differs from static auto-drafted GSTR-2B (₹{gstr2b_gst:,.2f}) "
                    f"by ₹{abs(gstr2a_to_gstr2b_diff):,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: Suppliers filed GSTR-1 after the monthly cut-off date (11th/13th), which updates GSTR-2A dynamically but only appears in next month's GSTR-2B.",
                ],
                "recommendation": "Review supplier filing timestamps. Use GSTR-2B as the statutory baseline for GSTR-3B Table 4(A) claims.",
            })

        # GSTR-2A vs GSTR-3B Table 4(A)
        if gstr3b_available and has_gstr2a and abs(gstr2a_to_gstr3b_diff) > 0.01:
            sev = "HIGH" if abs(gstr2a_to_gstr3b_diff) > 5000 else "MEDIUM"
            findings.append({
                "finding_id": "cf-gstr2a-gstr3b-diff",
                "category": "ITC_CLAIMED_VS_AVAILABLE",
                "severity": sev,
                "register_value": round(gstr2a_gst, 2),
                "gst_portal_value": gstr3b_eligible_itc,
                "difference": gstr2a_to_gstr3b_diff,
                "description": (
                    f"GSTR-2A available ITC (₹{gstr2a_gst:,.2f}) differs from "
                    f"GSTR-3B Table 4(A) eligible ITC claimed (₹{gstr3b_eligible_itc:,.2f}) "
                    f"by ₹{abs(gstr2a_to_gstr3b_diff):,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: ITC claimed in GSTR-3B exceeds what is available in GSTR-2A.",
                    "Hypothesis: Transition credit or RCM credit included in 4(A) claim.",
                    "Hypothesis: GSTR-2B (auto-drafted) figures used instead of GSTR-2A.",
                ],
                "recommendation": (
                    "Verify GSTR-3B Table 4(A) does not exceed GSTR-2A/2B totals without "
                    "a valid legal basis. Excess ITC claims may attract interest and enquiry."
                ),
            })

        # GSTR-2B vs GSTR-3B Table 4(A) (when GSTR-2B present)
        if gstr3b_available and has_gstr2b and gstr2b_to_gstr3b_diff is not None and abs(gstr2b_to_gstr3b_diff) > 0.01:
            sev = "HIGH" if abs(gstr2b_to_gstr3b_diff) > 5000 else "MEDIUM"
            findings.append({
                "finding_id": "cf-gstr2b-gstr3b-diff",
                "category": "GSTR2B_VS_GSTR3B_ITC_CLAIMED",
                "severity": sev,
                "register_value": round(gstr2b_gst, 2),
                "gst_portal_value": gstr3b_eligible_itc,
                "difference": gstr2b_to_gstr3b_diff,
                "description": (
                    f"GSTR-2B auto-drafted ITC (₹{gstr2b_gst:,.2f}) differs from "
                    f"GSTR-3B Table 4(A) eligible ITC claimed (₹{gstr3b_eligible_itc:,.2f}) "
                    f"by ₹{abs(gstr2b_to_gstr3b_diff):,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: Taxpayer claimed ITC in GSTR-3B based on internal books rather than auto-drafted GSTR-2B.",
                    "Hypothesis: RCM or import of goods ITC included in Table 4(A) not reflected in GSTR-2B B2B section.",
                ],
                "recommendation": (
                    "Cross-check GSTR-3B Table 4(A) against GSTR-2B auto-drafted statement. Maintain audit trail for any variances."
                ),
            })

        # ITC reversal note
        if gstr3b_available and gstr3b_itc_reversed > 0:
            findings.append({
                "finding_id": "cf-itc-reversal",
                "category": "ITC_REVERSAL_NOTE",
                "severity": "INFO",
                "register_value": gstr3b_eligible_itc,
                "gst_portal_value": gstr3b_net_itc,
                "difference": round(gstr3b_itc_reversed, 2),
                "description": (
                    f"GSTR-3B Table 4(B) shows ₹{gstr3b_itc_reversed:,.2f} of ITC reversed. "
                    f"Net ITC available in Electronic Credit Ledger: ₹{gstr3b_net_itc:,.2f}."
                ),
                "possible_causes": [
                    "Hypothesis: Ineligible ITC under Section 17(5) (blocked credits).",
                    "Hypothesis: Rule 42/43 reversal for exempt/non-business use.",
                    "Hypothesis: Provisional ITC reversal pending supplier filing.",
                ],
                "recommendation": "Confirm reversal basis with your GST consultant. Maintain documentation for each reversed ITC item.",
            })

    # GSTR-2B integration status finding
    if has_gstr2b:
        findings.append({
            "finding_id": "cf-gstr2b-status",
            "category": "DATA_AVAILABILITY",
            "severity": "INFO",
            "description": f"GSTR-2B static auto-drafted ITC statement is integrated and available for {resolved_period}.",
            "recommendation": "Use GSTR-2B figures for verifying Table 4(A) eligibility in GSTR-3B filing under Rule 36(4).",
        })
    else:
        findings.append({
            "finding_id": "cf-gstr2b-disclaimer",
            "category": "DATA_AVAILABILITY",
            "severity": "INFO",
            "description": "GSTR-2B dataset is not yet loaded for this business and tax period.",
            "recommendation": "Upload GSTR-2B CSV to enable static auto-drafted ITC comparison against GSTR-2A and GSTR-3B.",
        })

    return {
        "business_id": current_business.id,
        "tax_period": resolved_period,
        "gstr3b_data_available": gstr3b_available,
        "register_data_available": has_db_data,
        "gstr3b_summary": {
            "output_tax": gstr3b_output_tax,
            "eligible_itc": gstr3b_eligible_itc,
            "itc_reversed": gstr3b_itc_reversed,
            "net_itc": gstr3b_net_itc,
            "estimated_net_tax_payable": estimated_net_tax,
        },
        "register_sums": {
            "sales_register_gst": round(sales_reg_gst, 2),
            "gstr1_gst": round(gstr1_gst, 2),
            "purchase_register_gst": round(purchase_reg_gst, 2),
            "gstr2a_gst": round(gstr2a_gst, 2),
            "gstr2b_gst": round(gstr2b_gst, 2),
            "sales_register_taxable": round(sales_reg_tv, 2),
            "gstr1_taxable": round(gstr1_tv, 2),
            "purchase_register_taxable": round(purchase_reg_tv, 2),
            "gstr2a_taxable": round(gstr2a_tv, 2),
            "gstr2b_taxable": round(gstr2b_tv, 2),
        },
        "cross_form_differences": {
            "sales_register_vs_gstr1_gst": sales_to_gstr1_diff,
            "gstr1_vs_gstr3b_output_tax": gstr1_to_gstr3b_diff if gstr3b_available else None,
            "purchase_register_vs_gstr2a_gst": purchase_to_gstr2a_diff,
            "purchase_register_vs_gstr2b_gst": purchase_to_gstr2b_diff,
            "gstr2a_vs_gstr2b_gst": gstr2a_to_gstr2b_diff,
            "gstr2a_vs_gstr3b_itc": gstr2a_to_gstr3b_diff if gstr3b_available else None,
            "gstr2b_vs_gstr3b_itc": gstr2b_to_gstr3b_diff,
        },
        "findings": findings,
        "total_findings": len(findings),
        "note": (
            "Cross-form differences are reported as hypotheses for investigation only. "
            "They do not constitute confirmed compliance errors or proof of tax evasion. "
            "Output tax minus net ITC provides an indicative net tax estimate, not the complete statutory tax payable. "
            "Consult a qualified GST practitioner before making any return amendments."
        ),
    }
