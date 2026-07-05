"""
Database layer. Uses SQLAlchemy with SQLite by default (zero setup) but
DATABASE_URL can point at Postgres for production - swap it in .env and
`pip install psycopg2-binary`, no code changes needed.

Kept synchronous and simple on purpose: a restaurant's reservation/order
volume doesn't need async DB drivers, and calling these functions from the
async voice pipeline via asyncio.to_thread() keeps the websocket loop
non-blocking without adding SQLAlchemy-async complexity.
"""
from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def _id() -> str:
    return uuid.uuid4().hex[:12]


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(String, primary_key=True, default=_id)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # appetizer, main, dessert, drink
    description = Column(Text, default="")
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True)
    contains_allergens = Column(String, default="")  # comma separated, e.g. "nuts,dairy"
    is_vegetarian = Column(Boolean, default=False)
    is_vegan = Column(Boolean, default=False)


class DiningTable(Base):
    __tablename__ = "tables"

    id = Column(String, primary_key=True, default=_id)
    label = Column(String, nullable=False)  # "T1", "Patio 3"
    seats = Column(Integer, nullable=False)


class ReservationStatus(str, enum.Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(String, primary_key=True, default=_id)
    customer_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    party_size = Column(Integer, nullable=False)
    reservation_time = Column(DateTime, nullable=False)
    table_id = Column(String, ForeignKey("tables.id"), nullable=True)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.confirmed)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    table = relationship("DiningTable")


class OrderStatus(str, enum.Enum):
    placed = "placed"
    preparing = "preparing"
    ready = "ready"
    completed = "completed"
    cancelled = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=_id)
    customer_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    order_type = Column(String, default="pickup")  # pickup, delivery, dine-in
    status = Column(Enum(OrderStatus), default=OrderStatus.placed)
    total_price = Column(Float, default=0.0)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String, primary_key=True, default=_id)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(String, ForeignKey("menu_items.id"), nullable=False)
    menu_item_name = Column(String, nullable=False)  # denormalized snapshot
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    special_instructions = Column(Text, default="")

    order = relationship("Order", back_populates="items")


class CallLog(Base):
    """Transcript + metadata for every call, for QA and dispute resolution."""

    __tablename__ = "call_logs"

    id = Column(String, primary_key=True, default=_id)
    channel = Column(String, default="phone")  # phone | web
    caller_number = Column(String, default="")
    started_at = Column(DateTime, default=dt.datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    transcript = Column(Text, default="")  # newline separated "User: ..." / "Agent: ..."
    escalated = Column(Boolean, default=False)


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Session:
    return SessionLocal()
