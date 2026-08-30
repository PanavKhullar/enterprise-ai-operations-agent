from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    warehouse_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    name: Mapped[str] = mapped_column(String(100))

    region: Mapped[str] = mapped_column(String(50))

    capacity: Mapped[int] = mapped_column(Integer)


class Carrier(Base):
    __tablename__ = "carriers"

    carrier_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    name: Mapped[str] = mapped_column(String(100))


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id")
    )

    region: Mapped[str] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(
        DateTime
    )

    promised_at: Mapped[datetime] = mapped_column(
        DateTime
    )


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.order_id")
    )

    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id")
    )

    carrier_id: Mapped[str] = mapped_column(
        ForeignKey("carriers.carrier_id")
    )

    shipped_at: Mapped[datetime] = mapped_column(
        DateTime
    )

    delivered_at: Mapped[datetime] = mapped_column(
        DateTime
    )


class SLAEvent(Base):
    __tablename__ = "sla_events"

    event_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.order_id")
    )

    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id")
    )

    event_type: Mapped[str] = mapped_column(
        String(50)
    )

    expected_time: Mapped[datetime] = mapped_column(
        DateTime
    )

    actual_time: Mapped[datetime] = mapped_column(
        DateTime
    )

    delay_minutes: Mapped[float] = mapped_column(
        Float
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime
    )


class Investigation(Base):
    """Persisted record of a past agent investigation run."""

    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    question: Mapped[str] = mapped_column(Text)

    investigation_plan: Mapped[dict] = mapped_column(JSON)

    hypotheses: Mapped[dict] = mapped_column(JSON, nullable=True)

    evidence: Mapped[dict] = mapped_column(JSON)

    analysis: Mapped[str] = mapped_column(Text)

    recommendation: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )