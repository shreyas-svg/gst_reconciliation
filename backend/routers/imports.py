import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, delete
from sqlalchemy.orm import Session

from database import get_db
from models.models import Business, Gstr3bSummary, ImportAuditLog, ImportBatch, Invoice, User
from services.auth import get_current_business, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/imports", tags=["Import History & Undo"])


class UndoRequest(BaseModel):
    confirmed: bool = False
    notes: Optional[str] = None


def _get_counterpart_source(source_type: str) -> Optional[List[str]]:
    mapping = {
        "sales_register": ["gstr1"],
        "gstr1": ["sales_register"],
        "purchase_register": ["gstr2a", "gstr2b"],
        "gstr2a": ["purchase_register"],
        "gstr2b": ["purchase_register"],
    }
    return mapping.get(source_type)


@router.get("")
def list_import_batches(
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by batch status (COMPLETED, UNDONE)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    """
    List all import batches for the authenticated business.
    Tenant-isolated: Strictly filters by current_business.id.
    """
    query = select(ImportBatch).where(ImportBatch.business_id == current_business.id)

    if source_type:
        query = query.where(ImportBatch.source_type == source_type.strip().lower())
    if status_filter:
        query = query.where(ImportBatch.status == status_filter.strip().upper())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc()).offset(offset).limit(limit)
    batches = db.scalars(query).all()

    items = []
    for b in batches:
        if b.source_type == "gstr3b":
            active_count = db.scalar(
                select(func.count(Gstr3bSummary.id)).where(
                    Gstr3bSummary.business_id == current_business.id,
                    Gstr3bSummary.import_batch_id == b.batch_id,
                )
            ) or 0
            modified_count = 0
        else:
            active_count = db.scalar(
                select(func.count(Invoice.id)).where(
                    Invoice.business_id == current_business.id,
                    Invoice.import_batch_id == b.batch_id,
                )
            ) or 0
            modified_count = db.scalar(
                select(func.count(Invoice.id)).where(
                    Invoice.business_id == current_business.id,
                    Invoice.import_batch_id == b.batch_id,
                    Invoice.updated_at.is_not(None),
                )
            ) or 0

        can_undo = True
        undo_block_reason = None

        if b.status == "UNDONE":
            can_undo = False
            undo_block_reason = "Import batch has already been undone."
        elif active_count == 0:
            can_undo = False
            undo_block_reason = "No active records remain for this batch (all were duplicates, rejected, or removed)."
        elif modified_count > 0:
            can_undo = False
            undo_block_reason = f"{modified_count} record(s) in this batch were modified after import."

        items.append({
            "id": b.id,
            "batch_id": b.batch_id,
            "business_id": b.business_id,
            "source_type": b.source_type,
            "filename": b.filename,
            "total_rows": b.total_rows,
            "imported_rows": b.imported_rows,
            "duplicate_rows": b.duplicate_rows,
            "rejected_rows": b.rejected_rows,
            "active_records_count": active_count,
            "modified_records_count": modified_count,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "undone_at": b.undone_at.isoformat() if b.undone_at else None,
            "can_undo": can_undo,
            "undo_block_reason": undo_block_reason,
            "notes": b.notes,
        })

    return {
        "business_id": current_business.id,
        "business_name": current_business.name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
    }


@router.get("/{batch_id}")
def get_import_batch_details(
    batch_id: str,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    """
    Get detailed breakdown, record preview, and audit trail for a specific import batch.
    Tenant-isolated: Strictly verifies business ownership.
    """
    batch = db.scalar(
        select(ImportBatch).where(
            ImportBatch.batch_id == batch_id,
            ImportBatch.business_id == current_business.id,
        )
    )
    if not batch:
        # Check if batch belongs to another business to give precise forbidden response
        other_batch = db.scalar(select(ImportBatch).where(ImportBatch.batch_id == batch_id))
        if other_batch:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have access to this business's import batch.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import batch '{batch_id}' not found.",
        )

    preview_records = []
    counterpart_matches = 0
    modified_count = 0

    if batch.source_type == "gstr3b":
        summaries = db.scalars(
            select(Gstr3bSummary)
            .where(
                Gstr3bSummary.business_id == current_business.id,
                Gstr3bSummary.import_batch_id == batch.batch_id,
            )
            .order_by(Gstr3bSummary.id.asc())
        ).all()
        active_count = len(summaries)
        for s in summaries[:20]:
            preview_records.append({
                "id": s.id,
                "tax_period": s.tax_period,
                "output_tax": s.output_tax,
                "eligible_itc": s.eligible_itc,
                "itc_reversed": s.itc_reversed,
                "net_itc": s.net_itc,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })
    else:
        invoices = db.scalars(
            select(Invoice)
            .where(
                Invoice.business_id == current_business.id,
                Invoice.import_batch_id == batch.batch_id,
            )
            .order_by(Invoice.id.asc())
        ).all()
        active_count = len(invoices)
        modified_count = sum(1 for inv in invoices if inv.updated_at is not None)

        for inv in invoices[:20]:
            preview_records.append({
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "gstin": inv.gstin,
                "taxable_value": inv.taxable_value,
                "gst_amount": inv.gst_amount,
                "source": inv.source,
                "is_modified": inv.updated_at is not None,
            })

        # Check reconciliation counterpart matches
        counterpart_sources = _get_counterpart_source(batch.source_type)
        if counterpart_sources and invoices:
            inv_numbers = [inv.invoice_no for inv in invoices]
            if inv_numbers:
                match_count = db.scalar(
                    select(func.count(Invoice.id)).where(
                        Invoice.business_id == current_business.id,
                        Invoice.source.in_(counterpart_sources),
                        Invoice.invoice_no.in_(inv_numbers),
                    )
                ) or 0
                counterpart_matches = match_count

    # Fetch audit logs for this batch
    audit_logs = db.scalars(
        select(ImportAuditLog)
        .where(
            ImportAuditLog.business_id == current_business.id,
            ImportAuditLog.batch_id == batch.batch_id,
        )
        .order_by(ImportAuditLog.created_at.asc())
    ).all()

    can_undo = True
    undo_block_reason = None
    if batch.status == "UNDONE":
        can_undo = False
        undo_block_reason = "Import batch has already been undone."
    elif active_count == 0:
        can_undo = False
        undo_block_reason = "No active records remain for this batch."
    elif modified_count > 0:
        can_undo = False
        undo_block_reason = f"{modified_count} record(s) in this batch were modified after import."

    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
        "business": {
            "id": current_business.id,
            "name": current_business.name,
            "gstin": current_business.gstin,
        },
        "source_type": batch.source_type,
        "filename": batch.filename,
        "total_rows": batch.total_rows,
        "imported_rows": batch.imported_rows,
        "duplicate_rows": batch.duplicate_rows,
        "rejected_rows": batch.rejected_rows,
        "active_records_count": active_count,
        "modified_records_count": modified_count,
        "counterpart_matched_records": counterpart_matches,
        "status": batch.status,
        "can_undo": can_undo,
        "undo_block_reason": undo_block_reason,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "undone_at": batch.undone_at.isoformat() if batch.undone_at else None,
        "preview_records": preview_records,
        "total_preview_count": len(preview_records),
        "audit_logs": [
            {
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in audit_logs
        ],
    }


@router.get("/{batch_id}/preview-undo")
def preview_undo_import(
    batch_id: str,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    """
    Dry-run preview endpoint specifically for safe confirmation dialogs.
    Returns exact number of records that will be deleted and checks for blocking conditions.
    """
    batch = db.scalar(
        select(ImportBatch).where(
            ImportBatch.batch_id == batch_id,
            ImportBatch.business_id == current_business.id,
        )
    )
    if not batch:
        other = db.scalar(select(ImportBatch).where(ImportBatch.batch_id == batch_id))
        if other:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have access to this business's import batch.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import batch '{batch_id}' not found.",
        )

    if batch.source_type == "gstr3b":
        records_to_delete = db.scalar(
            select(func.count(Gstr3bSummary.id)).where(
                Gstr3bSummary.business_id == current_business.id,
                Gstr3bSummary.import_batch_id == batch.batch_id,
            )
        ) or 0
        modified_count = 0
        counterpart_matches = 0
    else:
        records_to_delete = db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.business_id == current_business.id,
                Invoice.import_batch_id == batch.batch_id,
            )
        ) or 0
        modified_count = db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.business_id == current_business.id,
                Invoice.import_batch_id == batch.batch_id,
                Invoice.updated_at.is_not(None),
            )
        ) or 0

        counterpart_matches = 0
        counterparts = _get_counterpart_source(batch.source_type)
        if counterparts and records_to_delete > 0:
            inv_nums = db.scalars(
                select(Invoice.invoice_no).where(
                    Invoice.business_id == current_business.id,
                    Invoice.import_batch_id == batch.batch_id,
                )
            ).all()
            if inv_nums:
                counterpart_matches = db.scalar(
                    select(func.count(Invoice.id)).where(
                        Invoice.business_id == current_business.id,
                        Invoice.source.in_(counterparts),
                        Invoice.invoice_no.in_(inv_nums),
                    )
                ) or 0

    can_undo = True
    block_reason = None

    if batch.status == "UNDONE":
        can_undo = False
        block_reason = "This import batch has already been undone."
    elif records_to_delete == 0:
        can_undo = False
        block_reason = "No records exist for this import batch to delete."
    elif modified_count > 0:
        can_undo = False
        block_reason = f"Cannot undo import: {modified_count} record(s) in this batch have been modified post-import."

    return {
        "batch_id": batch.batch_id,
        "filename": batch.filename,
        "source_type": batch.source_type,
        "business_id": current_business.id,
        "business_name": current_business.name,
        "records_to_delete": records_to_delete,
        "modified_count": modified_count,
        "counterpart_matched_records": counterpart_matches,
        "can_undo": can_undo,
        "block_reason": block_reason,
        "status": batch.status,
    }


@router.post("/{batch_id}/undo")
def undo_import_batch(
    batch_id: str,
    undo_req: Optional[UndoRequest] = None,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Safely undoes an import batch using an atomic database transaction.
    Guarantees:
    - Only records created by this batch are deleted.
    - Never deletes records from other batches or other businesses.
    - Pre-existing records and skipped duplicates are preserved.
    - GSTR-3B summary records are handled separately.
    - Blocked if records were modified post-import.
    - Requires explicit confirmation if records are matched in reconciliation.
    - Atomic rollback on failure.
    - Audit log entry created.
    """
    confirmed = undo_req.confirmed if undo_req else False
    notes = undo_req.notes if undo_req else None

    batch = db.scalar(
        select(ImportBatch).where(
            ImportBatch.batch_id == batch_id,
            ImportBatch.business_id == current_business.id,
        )
    )
    if not batch:
        other = db.scalar(select(ImportBatch).where(ImportBatch.batch_id == batch_id))
        if other:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to modify another business's import batch.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import batch '{batch_id}' not found.",
        )

    # 1. State check: Already undone?
    if batch.status == "UNDONE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import batch '{batch_id}' has already been undone.",
        )

    # 2. Safety checks
    if batch.source_type == "gstr3b":
        active_records = db.scalar(
            select(func.count(Gstr3bSummary.id)).where(
                Gstr3bSummary.business_id == current_business.id,
                Gstr3bSummary.import_batch_id == batch_id,
            )
        ) or 0
        if active_records == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No imported GSTR-3B summary records found for this batch to undo.",
            )
    else:
        # Check for post-import modifications
        modified_count = db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.business_id == current_business.id,
                Invoice.import_batch_id == batch_id,
                Invoice.updated_at.is_not(None),
            )
        ) or 0
        if modified_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot undo import batch: {modified_count} record(s) in this batch have been modified after import. To protect data integrity, batches with modified records cannot be automatically removed.",
            )

        active_records = db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.business_id == current_business.id,
                Invoice.import_batch_id == batch_id,
            )
        ) or 0
        if active_records == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No imported invoice records found for this batch to undo (all may have been duplicates or removed).",
            )

        # Check reconciliation counterpart matches
        counterparts = _get_counterpart_source(batch.source_type)
        if counterparts:
            inv_nums = db.scalars(
                select(Invoice.invoice_no).where(
                    Invoice.business_id == current_business.id,
                    Invoice.import_batch_id == batch_id,
                )
            ).all()
            if inv_nums:
                match_count = db.scalar(
                    select(func.count(Invoice.id)).where(
                        Invoice.business_id == current_business.id,
                        Invoice.source.in_(counterparts),
                        Invoice.invoice_no.in_(inv_nums),
                    )
                ) or 0
                if match_count > 0 and not confirmed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Confirmation required: {match_count} record(s) in this batch are actively matched in reconciliation against counterparty filings. Please confirm in the dialog to proceed with removing these reconciled records.",
                    )

    # 3. Perform atomic deletion in transaction
    try:
        deleted_count = 0
        if batch.source_type == "gstr3b":
            deleted_count = db.execute(
                delete(Gstr3bSummary).where(
                    Gstr3bSummary.business_id == current_business.id,
                    Gstr3bSummary.import_batch_id == batch_id,
                )
            ).rowcount
        else:
            deleted_count = db.execute(
                delete(Invoice).where(
                    Invoice.business_id == current_business.id,
                    Invoice.import_batch_id == batch_id,
                )
            ).rowcount

        batch.status = "UNDONE"
        batch.undone_at = datetime.utcnow()
        batch.undone_by_user_id = current_user.id
        if notes:
            batch.notes = ((batch.notes + " | ") if batch.notes else "") + f"Undo note: {notes.strip()}"

        audit_entry = ImportAuditLog(
            business_id=current_business.id,
            user_id=current_user.id,
            batch_id=batch_id,
            action="UNDO_IMPORT",
            details=f"Undid import batch '{batch_id}' ({batch.source_type}) from file '{batch.filename}'. Removed {deleted_count} record(s).",
        )
        db.add(audit_entry)
        db.commit()

        logger.info(
            "Successfully undone import batch %s for business %s. Removed %d records.",
            batch_id,
            current_business.id,
            deleted_count,
        )

        return {
            "success": True,
            "batch_id": batch_id,
            "filename": batch.filename,
            "source_type": batch.source_type,
            "business_id": current_business.id,
            "records_removed": deleted_count,
            "status": "UNDONE",
            "message": f"Successfully undone import batch '{batch_id}' for '{batch.filename}'. {deleted_count} record(s) were removed.",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Failed to undo import batch %s: %s", batch_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while undoing import batch: {str(exc)}",
        )
