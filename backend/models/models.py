from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))

    businesses: Mapped[list["Business"]] = relationship(
        back_populates="user"
    )


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    gstin: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user: Mapped["User"] = relationship(back_populates="businesses")
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="business"
    )
    import_batches: Mapped[list["ImportBatch"]] = relationship(
        back_populates="business"
    )
    gstr3b_summaries: Mapped[list["Gstr3bSummary"]] = relationship(
        back_populates="business"
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED")  # "COMPLETED", "UNDONE"
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    undone_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    undone_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="import_batches")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="import_batch")
    gstr3b_summaries: Mapped[list["Gstr3bSummary"]] = relationship(back_populates="import_batch")


class ImportAuditLog(Base):
    __tablename__ = "import_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(50))  # "IMPORT_CSV", "UNDO_IMPORT"
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class Gstr3bSummary(Base):
    __tablename__ = "gstr3b_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    tax_period: Mapped[str] = mapped_column(String(10), index=True)
    output_tax: Mapped[float] = mapped_column(Float, default=0.0)
    eligible_itc: Mapped[float] = mapped_column(Float, default=0.0)
    itc_reversed: Mapped[float] = mapped_column(Float, default=0.0)
    net_itc: Mapped[float] = mapped_column(Float, default=0.0)
    import_batch_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("import_batches.batch_id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    business: Mapped["Business"] = relationship(back_populates="gstr3b_summaries")
    import_batch: Mapped[Optional["ImportBatch"]] = relationship(back_populates="gstr3b_summaries")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_no: Mapped[str] = mapped_column(String(50), index=True)
    invoice_date: Mapped[date] = mapped_column(Date)
    gstin: Mapped[str] = mapped_column(String(15))
    taxable_value: Mapped[float] = mapped_column(Float)
    gst_amount: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id")
    )
    import_batch_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("import_batches.batch_id"), nullable=True, index=True
    )

    business: Mapped["Business"] = relationship(
        back_populates="invoices"
    )
    import_batch: Mapped[Optional["ImportBatch"]] = relationship(
        back_populates="invoices"
    )