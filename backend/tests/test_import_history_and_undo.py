import io
from datetime import date, datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from main import app
from database import SessionLocal
from models.models import Business, Gstr3bSummary, ImportAuditLog, ImportBatch, Invoice, User
from services.auth import create_access_token, hash_password

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_setup():
    db = SessionLocal()
    try:
        # User 1 and Business 1
        u1 = db.scalar(select(User).where(User.email == "undo_tester1@gst.local"))
        if not u1:
            u1 = User(
                name="Undo Tester 1",
                email="undo_tester1@gst.local",
                password=hash_password("Pass123!"),
            )
            db.add(u1)
            db.flush()

        b1 = db.scalar(select(Business).where(Business.gstin == "29UNDOT1111A1Z1"))
        if not b1:
            b1 = Business(
                name="Undo Enterprise 1",
                gstin="29UNDOT1111A1Z1",
                user_id=u1.id,
            )
            db.add(b1)
            db.flush()

        # User 2 and Business 2 (for tenant isolation tests)
        u2 = db.scalar(select(User).where(User.email == "undo_tester2@gst.local"))
        if not u2:
            u2 = User(
                name="Undo Tester 2",
                email="undo_tester2@gst.local",
                password=hash_password("Pass123!"),
            )
            db.add(u2)
            db.flush()

        b2 = db.scalar(select(Business).where(Business.gstin == "29UNDOT2222B2Z2"))
        if not b2:
            b2 = Business(
                name="Undo Enterprise 2",
                gstin="29UNDOT2222B2Z2",
                user_id=u2.id,
            )
            db.add(b2)
            db.flush()

        # Clean invoices and batches for these test businesses
        db.execute(delete(Invoice).where(Invoice.business_id.in_([b1.id, b2.id])))
        db.execute(delete(Gstr3bSummary).where(Gstr3bSummary.business_id.in_([b1.id, b2.id])))
        db.execute(delete(ImportAuditLog).where(ImportAuditLog.business_id.in_([b1.id, b2.id])))
        db.execute(delete(ImportBatch).where(ImportBatch.business_id.in_([b1.id, b2.id])))
        db.commit()

        t1 = create_access_token(u1.id, u1.email)
        h1 = {"Authorization": f"Bearer {t1}", "X-Business-ID": str(b1.id)}

        t2 = create_access_token(u2.id, u2.email)
        h2 = {"Authorization": f"Bearer {t2}", "X-Business-ID": str(b2.id)}

        return {
            "u1": u1,
            "b1": b1,
            "h1": h1,
            "u2": u2,
            "b2": b2,
            "h2": h2,
        }
    finally:
        db.close()


def test_upload_generates_batch_and_associates_records(client, test_setup):
    """Requirement 1: Every upload generates a batch ID and newly imported records are associated."""
    csv_content = (
        "invoice_no,customer_gstin,invoice_date,taxable_value,gst_amount\n"
        "INV-TEST-001,29ABCDE1234F1Z5,2026-07-01,15000,2700\n"
        "INV-TEST-002,29BCDEF2345G1Z6,2026-07-02,25000,4500\n"
    ).encode("utf-8")

    res = client.post(
        "/invoices/upload",
        files={"file": ("test_sales.csv", csv_content, "text/csv")},
        data={"source_type": "sales_register"},
        headers=test_setup["h1"],
    )
    assert res.status_code == 200
    data = res.json()
    assert "batch_id" in data
    assert data["batch_id"].startswith("imp_")
    assert data["imported"] == 2
    assert data["duplicates"] == 0

    batch_id = data["batch_id"]

    db = SessionLocal()
    try:
        # Verify batch row
        batch = db.scalar(select(ImportBatch).where(ImportBatch.batch_id == batch_id))
        assert batch is not None
        assert batch.business_id == test_setup["b1"].id
        assert batch.imported_rows == 2
        assert batch.status == "COMPLETED"

        # Verify newly imported records are tagged with batch_id
        invoices = db.scalars(select(Invoice).where(Invoice.import_batch_id == batch_id)).all()
        assert len(invoices) == 2
        assert {inv.invoice_no for inv in invoices} == {"INV-TEST-001", "INV-TEST-002"}

        # Verify audit log exists
        audit = db.scalar(select(ImportAuditLog).where(ImportAuditLog.batch_id == batch_id))
        assert audit is not None
        assert audit.action == "IMPORT_CSV"
    finally:
        db.close()


def test_skipped_duplicates_keep_original_batch(client, test_setup):
    """Requirement 1 & 3: Do not associate pre-existing records or skipped duplicates with a new batch."""
    # 1. First upload
    csv1 = (
        "invoice_no,customer_gstin,invoice_date,taxable_value,gst_amount\n"
        "INV-DUP-1,29ABCDE1234F1Z5,2026-07-01,10000,1800\n"
    ).encode("utf-8")
    r1 = client.post(
        "/invoices/upload",
        files={"file": ("first.csv", csv1, "text/csv")},
        data={"source_type": "sales_register"},
        headers=test_setup["h1"],
    ).json()
    batch1_id = r1["batch_id"]

    # 2. Second upload containing the same invoice + a new one
    csv2 = (
        "invoice_no,customer_gstin,invoice_date,taxable_value,gst_amount\n"
        "INV-DUP-1,29ABCDE1234F1Z5,2026-07-01,10000,1800\n"
        "INV-DUP-2,29ABCDE1234F1Z5,2026-07-02,20000,3600\n"
    ).encode("utf-8")
    r2 = client.post(
        "/invoices/upload",
        files={"file": ("second.csv", csv2, "text/csv")},
        data={"source_type": "sales_register"},
        headers=test_setup["h1"],
    ).json()
    batch2_id = r2["batch_id"]

    assert r2["imported"] == 1
    assert r2["duplicates"] == 1

    db = SessionLocal()
    try:
        inv1 = db.scalar(select(Invoice).where(Invoice.invoice_no == "INV-DUP-1", Invoice.business_id == test_setup["b1"].id))
        inv2 = db.scalar(select(Invoice).where(Invoice.invoice_no == "INV-DUP-2", Invoice.business_id == test_setup["b1"].id))

        # INV-DUP-1 MUST retain batch1_id, NOT batch2_id
        assert inv1.import_batch_id == batch1_id
        # INV-DUP-2 has batch2_id
        assert inv2.import_batch_id == batch2_id
    finally:
        db.close()


def test_undo_valid_import_removes_only_batch_records(client, test_setup):
    """Requirement 3 & 4: Undoing removes only records from that batch and preserves others."""
    # Pre-existing invoice without batch
    db = SessionLocal()
    try:
        pre_existing = Invoice(
            invoice_no="INV-PRE-EXISTING",
            invoice_date=datetime(2026, 7, 1).date(),
            gstin="29ABCDE1234F1Z5",
            taxable_value=5000.0,
            gst_amount=900.0,
            source="sales_register",
            business_id=test_setup["b1"].id,
            import_batch_id=None,
        )
        db.add(pre_existing)
        db.commit()
    finally:
        db.close()

    # Upload a batch
    csv_bytes = (
        "invoice_no,customer_gstin,invoice_date,taxable_value,gst_amount\n"
        "INV-UNDO-A,29ABCDE1234F1Z5,2026-07-01,10000,1800\n"
        "INV-UNDO-B,29ABCDE1234F1Z5,2026-07-02,20000,3600\n"
    ).encode("utf-8")
    upload_res = client.post(
        "/invoices/upload",
        files={"file": ("undo_test.csv", csv_bytes, "text/csv")},
        data={"source_type": "sales_register"},
        headers=test_setup["h1"],
    ).json()
    batch_id = upload_res["batch_id"]

    # Preview undo
    preview_res = client.get(f"/imports/{batch_id}/preview-undo", headers=test_setup["h1"])
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["records_to_delete"] == 2
    assert preview["can_undo"] is True

    # Perform undo
    undo_res = client.post(f"/imports/{batch_id}/undo", json={"confirmed": True}, headers=test_setup["h1"])
    assert undo_res.status_code == 200
    undo_data = undo_res.json()
    assert undo_data["success"] is True
    assert undo_data["records_removed"] == 2
    assert undo_data["status"] == "UNDONE"

    # Verify database state
    db = SessionLocal()
    try:
        # Pre-existing invoice must still exist!
        still_there = db.scalar(select(Invoice).where(Invoice.invoice_no == "INV-PRE-EXISTING"))
        assert still_there is not None

        # Batch records must be gone
        deleted_invoices = db.scalars(select(Invoice).where(Invoice.import_batch_id == batch_id)).all()
        assert len(deleted_invoices) == 0

        # Batch record is marked UNDONE
        batch = db.scalar(select(ImportBatch).where(ImportBatch.batch_id == batch_id))
        assert batch.status == "UNDONE"
        assert batch.undone_at is not None

        # Audit log for undo exists
        undo_audit = db.scalar(
            select(ImportAuditLog).where(
                ImportAuditLog.batch_id == batch_id,
                ImportAuditLog.action == "UNDO_IMPORT",
            )
        )
        assert undo_audit is not None
        assert "Removed 2 record(s)" in undo_audit.details
    finally:
        db.close()


def test_tenant_isolation_cannot_view_or_undo_other_business(client, test_setup):
    """Requirement 3: Never delete records belonging to another business; strictly enforce auth."""
    # Business 1 uploads a file
    csv_bytes = (
        "invoice_no,customer_gstin,invoice_date,taxable_value,gst_amount\n"
        "INV-BIZ1-ONLY,29ABCDE1234F1Z5,2026-07-01,10000,1800\n"
    ).encode("utf-8")
    b1_upload = client.post(
        "/invoices/upload",
        files={"file": ("biz1.csv", csv_bytes, "text/csv")},
        data={"source_type": "sales_register"},
        headers=test_setup["h1"],
    ).json()
    batch_id = b1_upload["batch_id"]

    # User 2 attempts to view Business 1's batch details -> 403 Forbidden
    detail_res = client.get(f"/imports/{batch_id}", headers=test_setup["h2"])
    assert detail_res.status_code == 403

    # User 2 attempts to preview undo Business 1's batch -> 403 Forbidden
    prev_res = client.get(f"/imports/{batch_id}/preview-undo", headers=test_setup["h2"])
    assert prev_res.status_code == 403

    # User 2 attempts to undo Business 1's batch -> 403 Forbidden
    undo_res = client.post(f"/imports/{batch_id}/undo", json={"confirmed": True}, headers=test_setup["h2"])
    assert undo_res.status_code == 403

    # Verify Business 1's record is completely safe and NOT deleted
    db = SessionLocal()
    try:
        inv = db.scalar(select(Invoice).where(Invoice.invoice_no == "INV-BIZ1-ONLY"))
        assert inv is not None
        assert inv.business_id == test_setup["b1"].id
    finally:
        db.close()


def test_repeated_undo_attempts_rejected(client, test_setup):
    """Requirement 5: Test repeated undo attempts are safely rejected."""
    csv_bytes = (
        "invoice_no,customer_gstin,invoice_date,taxable_value,gst_amount\n"
        "INV-REP-1,29ABCDE1234F1Z5,2026-07-01,10000,1800\n"
    ).encode("utf-8")
    r = client.post(
        "/invoices/upload",
        files={"file": ("rep.csv", csv_bytes, "text/csv")},
        data={"source_type": "sales_register"},
        headers=test_setup["h1"],
    ).json()
    batch_id = r["batch_id"]

    # First undo -> 200 OK
    u1 = client.post(f"/imports/{batch_id}/undo", json={"confirmed": True}, headers=test_setup["h1"])
    assert u1.status_code == 200

    # Second undo -> 400 Bad Request
    u2 = client.post(f"/imports/{batch_id}/undo", json={"confirmed": True}, headers=test_setup["h1"])
    assert u2.status_code == 400
    assert "already been undone" in u2.json()["detail"].lower()


def test_protect_against_deleting_modified_records(client, test_setup):
    """Requirement 3: Protect against accidental deletion of records that have been modified post-import."""
    csv_bytes = (
        "invoice_no,customer_gstin,invoice_date,taxable_value,gst_amount\n"
        "INV-MOD-1,29ABCDE1234F1Z5,2026-07-01,10000,1800\n"
    ).encode("utf-8")
    r = client.post(
        "/invoices/upload",
        files={"file": ("mod.csv", csv_bytes, "text/csv")},
        data={"source_type": "sales_register"},
        headers=test_setup["h1"],
    ).json()
    batch_id = r["batch_id"]

    # Mark the invoice as modified
    db = SessionLocal()
    try:
        inv = db.scalar(select(Invoice).where(Invoice.invoice_no == "INV-MOD-1"))
        inv.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    # Attempt undo -> MUST BE BLOCKED
    undo_res = client.post(f"/imports/{batch_id}/undo", json={"confirmed": True}, headers=test_setup["h1"])
    assert undo_res.status_code == 400
    assert "modified after import" in undo_res.json()["detail"].lower()

    # Verify invoice was NOT deleted
    db = SessionLocal()
    try:
        inv = db.scalar(select(Invoice).where(Invoice.invoice_no == "INV-MOD-1"))
        assert inv is not None
    finally:
        db.close()


def test_gstr3b_summary_import_and_undo_separately(client, test_setup):
    """Requirement 3 & 4: GSTR-3B summary uploads handled separately and CSV files in data/ not deleted."""
    gstr3b_csv_path = DATA_DIR / "gstr3b.csv"
    assert gstr3b_csv_path.exists(), "data/gstr3b.csv must exist"
    original_csv_mtime = gstr3b_csv_path.stat().st_mtime

    csv_text = "tax_period,output_tax,eligible_itc,itc_reversed,net_itc\n2026-11,98000,32000,1500,30500\n"
    res = client.post(
        "/invoices/upload",
        files={"file": ("gstr3b_nov.csv", csv_text.encode("utf-8"), "text/csv")},
        data={"source_type": "gstr3b"},
        headers=test_setup["h1"],
    )
    assert res.status_code == 200
    batch_id = res.json()["batch_id"]

    db = SessionLocal()
    try:
        summary = db.scalar(
            select(Gstr3bSummary).where(
                Gstr3bSummary.business_id == test_setup["b1"].id,
                Gstr3bSummary.import_batch_id == batch_id,
            )
        )
        assert summary is not None
        assert summary.tax_period == "2026-11"
        assert summary.output_tax == 98000.0
    finally:
        db.close()

    # Undo GSTR-3B batch
    undo_res = client.post(f"/imports/{batch_id}/undo", json={"confirmed": True}, headers=test_setup["h1"])
    assert undo_res.status_code == 200
    assert undo_res.json()["success"] is True

    # Verify DB record removed
    db = SessionLocal()
    try:
        summary_after = db.scalar(
            select(Gstr3bSummary).where(
                Gstr3bSummary.business_id == test_setup["b1"].id,
                Gstr3bSummary.import_batch_id == batch_id,
            )
        )
        assert summary_after is None
    finally:
        db.close()

    # Requirement 4: DO NOT delete CSV files from project's data directory as a side effect
    assert gstr3b_csv_path.exists(), "data/gstr3b.csv must NEVER be deleted by undo operations"
