from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


# ─── Tables ─────────────────────────────────────────────────────

class TableResponse(BaseModel):
    id: int
    table_number: int
    capacity: int
    is_available: bool
    location: Optional[str] = None


# ─── Reservations ───────────────────────────────────────────────

class ReservationCreate(BaseModel):
    customer_name: str
    phone: str
    email: Optional[str] = None
    party_size: int
    reservation_date: date
    reservation_time: time
    special_requests: Optional[str] = None


class ReservationResponse(BaseModel):
    id: int
    customer_name: str
    phone: str
    email: Optional[str] = None
    party_size: int
    reservation_date: date
    reservation_time: time
    status: str
    special_requests: Optional[str] = None
    table_id: Optional[int] = None

    model_config = {"from_attributes": True}


class AvailabilityRequest(BaseModel):
    date: date
    time: time
    party_size: int


class AvailabilityResponse(BaseModel):
    available: bool
    suggested_tables: list[TableResponse] = []


# ─── Menu ───────────────────────────────────────────────────────

class MenuItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Decimal
    category: str
    ingredients: Optional[str] = None
    allergens: Optional[str] = None
    is_available: bool
    is_spicy: bool
    is_vegetarian: bool
    is_vegan: bool
    is_gluten_free: bool

    model_config = {"from_attributes": True}


# ─── Orders ─────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int
    special_instructions: Optional[str] = None


class OrderCreate(BaseModel):
    customer_name: str
    phone: str
    items: list[OrderItemCreate]
    notes: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: int
    menu_item_id: int
    menu_item_name: str
    quantity: int
    unit_price: Decimal
    special_instructions: Optional[str] = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: str
    customer_name: str
    phone: str
    status: str
    total: Decimal
    notes: Optional[str] = None
    items: list[OrderItemResponse] = []
    created_at: str

    model_config = {"from_attributes": True}
