import enum
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Enum, ForeignKey, String, Text, Numeric, Boolean, Date, Time, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReservationStatus(str, enum.Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    preparing = "preparing"
    ready = "ready"
    delivered = "delivered"
    cancelled = "cancelled"


class MenuCategory(str, enum.Enum):
    appetizer = "appetizer"
    main_course = "main_course"
    pasta = "pasta"
    pizza = "pizza"
    dessert = "dessert"
    beverage = "beverage"
    side = "side"


# ─── Restaurant Tables ───────────────────────────────────────────

class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_number: Mapped[int] = mapped_column(unique=True, nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    location: Mapped[str | None] = mapped_column(String(100), default=None)  # e.g. "patio", "window", "bar"

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="table")

    def __repr__(self) -> str:
        return f"<Table {self.table_number} (capacity={self.capacity})>"


# ─── Reservations ───────────────────────────────────────────────

class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    party_size: Mapped[int] = mapped_column(nullable=False)
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False)
    reservation_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.confirmed, nullable=False
    )
    special_requests: Mapped[str | None] = mapped_column(Text, default=None)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("restaurant_tables.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    table: Mapped[RestaurantTable | None] = relationship(back_populates="reservations")

    def __repr__(self) -> str:
        return f"<Reservation {self.customer_name} ({self.party_size}pax @ {self.reservation_time})>"


# ─── Menu Items ─────────────────────────────────────────────────

class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    category: Mapped[MenuCategory] = mapped_column(
        Enum(MenuCategory), nullable=False
    )
    ingredients: Mapped[str | None] = mapped_column(Text, default=None)
    allergens: Mapped[str | None] = mapped_column(Text, default=None)  # comma-separated
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_spicy: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vegan: Mapped[bool] = mapped_column(Boolean, default=False)
    is_gluten_free: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(500), default=None)

    def __repr__(self) -> str:
        return f"<MenuItem {self.name} (${self.price})>"


# ─── Orders ─────────────────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.pending, nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    square_order_id: Mapped[str | None] = mapped_column(String(100), default=None)  # Square POS reference

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Order {self.id} ({self.customer_name} — ${self.total})>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    special_instructions: Mapped[str | None] = mapped_column(Text, default=None)

    order: Mapped[Order] = relationship(back_populates="items")
    menu_item: Mapped[MenuItem] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return f"<OrderItem x{self.quantity} of {self.menu_item_id}>"
