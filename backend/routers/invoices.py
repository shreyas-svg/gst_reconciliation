import io
import uuid
from datetime import datetime
from typing import List, Optional
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pathlib import Path
from database import get_db
from models.models import Business, Gstr3bSummary, ImportAuditLog, ImportBatch, Invoice, User
from services.auth import get_current_business, get_current_user
from services.validation import (
    normalize_gstr3b_dataframe,
    normalize_invoice_dataframe,
    parse_date_safely,
    validate_gstr3b_row,
    validate_invoice_row,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("")
def list_invoices(
    source: Optional[str] = Query(None, description="Filter by source (sales_register, gstr1, etc.)"),
    gstin: Optional[str] = Query(None, description="Filter by customer or supplier GSTIN"),
    search: Optional[str] = Query(None, description="Search by invoice number or GSTIN"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    query = select(Invoice).where(Invoice.business_id == current_business.id)

    if source:
        query = query.where(Invoice.source == source)
    if gstin:
        query = query.where(Invoice.gstin.ilike(f"%{gstin.strip()}%"))
    if search:
        s = f"%{search.strip()}%"
        query = query.where((Invoice.invoice_no.ilike(s)) | (Invoice.gstin.ilike(s)))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).offset(offset).limit(limit)
    invoices = db.scalars(query).all()

    return {
        "business_id": current_business.id,
        "business_name": current_business.name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "gstin": inv.gstin,
                "taxable_value": inv.taxable_value,
                "gst_amount": inv.gst_amount,
                "source": inv.source,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "business_id": inv.business_id,
                "import_batch_id": inv.import_batch_id,
            }
            for inv in invoices
        ],
    }


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: int,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.business_id == current_business.id,
        )
    )
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    return {
        "id": invoice.id,
        "invoice_no": invoice.invoice_no,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "gstin": invoice.gstin,
        "taxable_value": invoice.taxable_value,
        "gst_amount": invoice.gst_amount,
        "source": invoice.source,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "import_batch_id": invoice.import_batch_id,
        "business": {
            "id": current_business.id,
            "name": current_business.name,
            "gstin": current_business.gstin,
        },
    }


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    source_type: str = Form(..., description="sales_register, gstr1, purchase_register, gstr2a, gstr2b, or gstr3b"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_sources = {"sales_register", "gstr1", "purchase_register", "gstr2a", "gstr2b", "gstr3b"}
    norm_source = source_type.strip().lower()
    if norm_source not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type '{source_type}'. Must be one of {sorted(list(valid_sources))}",
        )

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files (.csv) are supported for upload",
        )

    try:
        content = await file.read()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        df = pd.read_csv(io.StringIO(text))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV file: {str(e)}",
        )

    # Strip any stray BOM or leading/trailing whitespace from column names
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]

    batch_id = f"imp_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

    if df.empty:
        # Create empty batch record for transparency
        empty_batch = ImportBatch(
            batch_id=batch_id,
            business_id=current_business.id,
            source_type=norm_source,
            filename=file.filename or f"{norm_source}.csv",
            total_rows=0,
            imported_rows=0,
            duplicate_rows=0,
            rejected_rows=0,
            status="COMPLETED",
            notes="Empty CSV file",
        )
        db.add(empty_batch)
        db.commit()

        return {
            "batch_id": batch_id,
            "file_name": file.filename,
            "source_type": norm_source,
            "business_id": current_business.id,
            "total_records": 0,
            "imported": 0,
            "duplicates": 0,
            "invalid_records": 0,
            "rejected": 0,
            "validation_findings": 0,
            "errors": [],
            "message": "CSV file was empty. No records imported.",
        }

    # ── GSTR-3B Summary Data Handling (Treated as monthly summary level, not invoice level) ──
    if norm_source == "gstr3b":
        norm_df, missing_cols = normalize_gstr3b_dataframe(df)
        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GSTR-3B upload validation error: {' | '.join(missing_cols)}",
            )

        total_records = len(norm_df)
        imported = 0
        duplicates = 0
        rejected = 0
        validation_errors: List[str] = []

        # Create import batch tracking entry
        batch = ImportBatch(
            batch_id=batch_id,
            business_id=current_business.id,
            source_type="gstr3b",
            filename=file.filename or "gstr3b.csv",
            total_rows=total_records,
            imported_rows=0,
            duplicate_rows=0,
            rejected_rows=0,
            status="COMPLETED",
        )
        db.add(batch)
        db.flush()

        # Load existing summary file if available for file synchronization
        gstr3b_path = DATA_DIR / "gstr3b.csv"
        existing_df = pd.DataFrame()
        if gstr3b_path.exists():
            try:
                existing_df = pd.read_csv(gstr3b_path, encoding="utf-8-sig")
            except Exception:
                existing_df = pd.DataFrame()

        rows_to_save = existing_df.to_dict("records") if not existing_df.empty else []

        for idx, row in norm_df.iterrows():
            row_dict = row.to_dict()
            is_valid, errs = validate_gstr3b_row(row_dict, idx + 1)
            if not is_valid:
                rejected += 1
                validation_errors.extend(errs)
                continue

            period = str(row_dict["tax_period"]).strip()
            out_tax = float(row_dict["output_tax"])
            el_itc = float(row_dict["eligible_itc"])
            itc_rev = float(row_dict.get("itc_reversed", 0.0) or 0.0)
            net_itc = float(row_dict.get("net_itc", el_itc - itc_rev))

            # Database duplicate check for active business
            existing_db_summary = db.scalar(
                select(Gstr3bSummary).where(
                    Gstr3bSummary.business_id == current_business.id,
                    Gstr3bSummary.tax_period == period,
                )
            )
            if existing_db_summary and (
                float(existing_db_summary.output_tax) == out_tax
                and float(existing_db_summary.eligible_itc) == el_itc
                and float(existing_db_summary.itc_reversed) == itc_rev
                and float(existing_db_summary.net_itc) == net_itc
            ):
                duplicates += 1
                continue

            # Store in database associated with this batch
            if existing_db_summary:
                # Update existing record and track update
                existing_db_summary.output_tax = out_tax
                existing_db_summary.eligible_itc = el_itc
                existing_db_summary.itc_reversed = itc_rev
                existing_db_summary.net_itc = net_itc
                existing_db_summary.import_batch_id = batch_id
            else:
                summary_record = Gstr3bSummary(
                    business_id=current_business.id,
                    tax_period=period,
                    output_tax=out_tax,
                    eligible_itc=el_itc,
                    itc_reversed=itc_rev,
                    net_itc=net_itc,
                    import_batch_id=batch_id,
                )
                db.add(summary_record)

            # Update file rows for compatibility with demo readers
            match_idx = None
            for i, existing_row in enumerate(rows_to_save):
                if str(existing_row.get("tax_period")).strip() == period:
                    match_idx = i
                    break

            summary_item = {
                "tax_period": period,
                "output_tax": out_tax,
                "eligible_itc": el_itc,
                "itc_reversed": itc_rev,
                "net_itc": net_itc,
            }
            if match_idx is not None:
                rows_to_save[match_idx] = summary_item
            else:
                rows_to_save.append(summary_item)

            imported += 1

        if imported > 0:
            try:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(rows_to_save).to_csv(gstr3b_path, index=False)
            except Exception as write_err:
                logger.warning("Failed to sync GSTR-3B CSV file: %s", write_err)

        batch.imported_rows = imported
        batch.duplicate_rows = duplicates
        batch.rejected_rows = rejected

        audit = ImportAuditLog(
            business_id=current_business.id,
            user_id=current_user.id,
            batch_id=batch_id,
            action="IMPORT_CSV",
            details=f"Imported {imported} of {total_records} GSTR-3B monthly summary period(s) from '{file.filename}'.",
        )
        db.add(audit)
        db.commit()

        return {
            "batch_id": batch_id,
            "file_name": file.filename,
            "source_type": "gstr3b",
            "business_id": current_business.id,
            "total_records": total_records,
            "imported": imported,
            "duplicates": duplicates,
            "invalid_records": rejected,
            "rejected": rejected,
            "validation_findings": len(validation_errors),
            "errors": validation_errors[:50],
            "message": f"Processed {total_records} GSTR-3B period(s): {imported} imported/updated, {duplicates} duplicates, {rejected} rejected ({len(validation_errors)} findings).",
        }

    # ── Invoice Register Handling (sales_register, gstr1, purchase_register, gstr2a, gstr2b) ──
    norm_df, missing_cols = normalize_invoice_dataframe(df, norm_source)
    if missing_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV schema validation error: {' | '.join(missing_cols)}",
        )

    total_records = len(norm_df)
    imported = 0
    duplicates = 0
    rejected = 0
    validation_errors: List[str] = []
    seen_in_batch = set()

    # Create import batch tracking entry
    batch = ImportBatch(
        batch_id=batch_id,
        business_id=current_business.id,
        source_type=norm_source,
        filename=file.filename or f"{norm_source}.csv",
        total_rows=total_records,
        imported_rows=0,
        duplicate_rows=0,
        rejected_rows=0,
        status="COMPLETED",
    )
    db.add(batch)
    db.flush()

    for idx, row in norm_df.iterrows():
        row_dict = row.to_dict()
        is_valid, errs = validate_invoice_row(row_dict, idx + 1)
        if not is_valid:
            rejected += 1
            validation_errors.extend(errs)
            continue

        invoice_no = str(row_dict["invoice_no"]).strip()
        gstin = str(row_dict.get("gstin") or "").strip().upper()

        inv_date = parse_date_safely(row_dict["invoice_date"])
        if not inv_date:
            rejected += 1
            validation_errors.append(f"Row {idx + 1}: Unrecognized date format '{row_dict['invoice_date']}'")
            continue

        try:
            taxable_value = float(row_dict["taxable_value"])
            gst_amount = float(row_dict["gst_amount"])
        except (ValueError, TypeError):
            rejected += 1
            validation_errors.append(f"Row {idx + 1}: Invalid numeric taxable_value or gst_amount")
            continue

        # Intra-batch duplicate check
        batch_key = (invoice_no, norm_source)
        if batch_key in seen_in_batch:
            duplicates += 1
            continue

        # Database duplicate check for active business
        existing = db.scalar(
            select(Invoice).where(
                Invoice.invoice_no == invoice_no,
                Invoice.business_id == current_business.id,
                Invoice.source == norm_source,
            )
        )
        if existing:
            # DO NOT re-associate pre-existing record with the new batch
            duplicates += 1
            seen_in_batch.add(batch_key)
            continue

        # Associate newly imported database record with its import batch ID
        invoice = Invoice(
            invoice_no=invoice_no,
            invoice_date=inv_date,
            gstin=gstin,
            taxable_value=taxable_value,
            gst_amount=gst_amount,
            source=norm_source,
            business_id=current_business.id,
            import_batch_id=batch_id,
        )
        db.add(invoice)
        seen_in_batch.add(batch_key)
        imported += 1

    batch.imported_rows = imported
    batch.duplicate_rows = duplicates
    batch.rejected_rows = rejected

    audit = ImportAuditLog(
        business_id=current_business.id,
        user_id=current_user.id,
        batch_id=batch_id,
        action="IMPORT_CSV",
        details=f"Imported {imported} of {total_records} invoice(s) from '{file.filename}' for source '{norm_source}'.",
    )
    db.add(audit)
    db.commit()

    return {
        "batch_id": batch_id,
        "file_name": file.filename,
        "source_type": norm_source,
        "business_id": current_business.id,
        "total_records": total_records,
        "imported": imported,
        "duplicates": duplicates,
        "invalid_records": rejected,
        "rejected": rejected,
        "validation_findings": len(validation_errors),
        "errors": validation_errors[:50],  # Cap preview errors
        "message": f"Processed {total_records} records: {imported} imported, {duplicates} duplicates, {rejected} rejected ({len(validation_errors)} findings).",
    }


