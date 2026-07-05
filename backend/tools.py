"""
The tool layer: what Gemini is allowed to *do*, and the code that actually
does it against the restaurant database.

FUNCTION_DECLARATIONS is sent to Gemini at session start so it knows what
tools exist. execute_tool() is called by gemini_session.py whenever Gemini
requests a tool_call. Keep these functions fast - anything slow (an external
POS call, a payment charge) should be marked NON_BLOCKING in its declaration
so the model keeps talking while it runs in the background.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from config import RESTAURANT_ADDRESS, RESTAURANT_HOURS, RESTAURANT_NAME, RESTAURANT_PHONE
from db import (
    CallLog,
    DiningTable,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    Reservation,
    ReservationStatus,
)

# ---------------------------------------------------------------------------
# Tool schema sent to Gemini. Keep descriptions concrete - the model reasons
# directly off these strings when deciding which tool to call and how to
# fill its arguments.
# ---------------------------------------------------------------------------
FUNCTION_DECLARATIONS = [
    {
        "name": "get_restaurant_info",
        "description": (
            "Get the restaurant's name, hours, address, and phone number. "
            "Call this whenever the caller asks about hours, location, or "
            "how to reach the restaurant."
        ),
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "search_menu",
        "description": (
            "Search the menu by category and/or dietary need. Use this to "
            "answer any question about what food/drinks are available, "
            "prices, ingredients, or allergens. Call with no filters to "
            "get the full menu."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "appetizer, main, dessert, or drink. Omit for all categories.",
                },
                "vegetarian_only": {"type": "BOOLEAN"},
                "vegan_only": {"type": "BOOLEAN"},
            },
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Check whether a table is available for a given party size, "
            "date, and time. Always call this BEFORE create_reservation."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "party_size": {"type": "INTEGER"},
                "date": {"type": "STRING", "description": "YYYY-MM-DD"},
                "time": {"type": "STRING", "description": "24-hour HH:MM, e.g. 19:30"},
            },
            "required": ["party_size", "date", "time"],
        },
    },
    {
        "name": "create_reservation",
        "description": (
            "Book a table. Only call this after check_availability has "
            "confirmed a table is free, and after you have the customer's "
            "name and a phone number to send the confirmation to."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_name": {"type": "STRING"},
                "phone_number": {"type": "STRING"},
                "party_size": {"type": "INTEGER"},
                "date": {"type": "STRING", "description": "YYYY-MM-DD"},
                "time": {"type": "STRING", "description": "24-hour HH:MM"},
                "notes": {"type": "STRING", "description": "Allergies, special occasion, seating request, etc."},
            },
            "required": ["customer_name", "phone_number", "party_size", "date", "time"],
        },
    },
    {
        "name": "cancel_reservation",
        "description": "Cancel an existing reservation by phone number and reservation date.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "phone_number": {"type": "STRING"},
                "date": {"type": "STRING", "description": "YYYY-MM-DD"},
            },
            "required": ["phone_number", "date"],
        },
    },
    {
        "name": "add_item_to_order",
        "description": (
            "Add one menu item to the customer's current order. Call once "
            "per distinct item (call again with a new quantity if they "
            "change their mind rather than guessing). Look up exact item "
            "names with search_menu first if you're unsure of spelling."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING"},
                "quantity": {"type": "INTEGER"},
                "special_instructions": {"type": "STRING"},
            },
            "required": ["item_name", "quantity"],
        },
    },
    {
        "name": "place_order",
        "description": (
            "Finalize and submit the current order. Call this only after "
            "confirming the full order back to the customer out loud and "
            "getting their name, phone number, and pickup vs delivery."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_name": {"type": "STRING"},
                "phone_number": {"type": "STRING"},
                "order_type": {"type": "STRING", "description": "pickup or delivery"},
            },
            "required": ["customer_name", "phone_number", "order_type"],
        },
    },
    {
        "name": "transfer_to_human",
        "description": (
            "Escalate the call to restaurant staff. Use this for complaints, "
            "large parties (8+), special events, anything you are not "
            "confident handling, or if the customer explicitly asks for a "
            "human."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "reason": {"type": "STRING"},
            },
            "required": ["reason"],
        },
    },
]

# Per-call scratch space for items being added before an order is placed.
# Keyed by call/session id so concurrent calls don't collide.
_pending_orders: dict[str, list[dict[str, Any]]] = {}


def _fmt_menu_item(m: MenuItem) -> dict:
    return {
        "name": m.name,
        "category": m.category,
        "description": m.description,
        "price": m.price,
        "vegetarian": m.is_vegetarian,
        "vegan": m.is_vegan,
        "allergens": m.contains_allergens,
    }


def execute_tool(session_id: str, db: Session, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool_call by name. Always returns a JSON-serializable dict."""

    if name == "get_restaurant_info":
        return {
            "name": RESTAURANT_NAME,
            "hours": RESTAURANT_HOURS,
            "address": RESTAURANT_ADDRESS,
            "phone": RESTAURANT_PHONE,
        }

    if name == "search_menu":
        q = db.query(MenuItem).filter(MenuItem.is_available.is_(True))
        category = args.get("category")
        if category:
            q = q.filter(MenuItem.category == category.lower())
        if args.get("vegetarian_only"):
            q = q.filter(MenuItem.is_vegetarian.is_(True))
        if args.get("vegan_only"):
            q = q.filter(MenuItem.is_vegan.is_(True))
        items = q.all()
        return {"items": [_fmt_menu_item(m) for m in items]}

    if name == "check_availability":
        party_size = int(args["party_size"])
        when = _parse_dt(args["date"], args["time"])
        available = _find_available_table(db, party_size, when)
        return {
            "available": available is not None,
            "table": available.label if available else None,
        }

    if name == "create_reservation":
        party_size = int(args["party_size"])
        when = _parse_dt(args["date"], args["time"])
        table = _find_available_table(db, party_size, when)
        if table is None:
            return {"success": False, "reason": "No table available for that time/party size."}
        res = Reservation(
            customer_name=args["customer_name"],
            phone_number=args["phone_number"],
            party_size=party_size,
            reservation_time=when,
            table_id=table.id,
            notes=args.get("notes", ""),
        )
        db.add(res)
        db.commit()
        return {
            "success": True,
            "reservation_id": res.id,
            "table": table.label,
            "confirmation_summary": (
                f"{args['customer_name']}, party of {party_size}, "
                f"{when.strftime('%A %B %d at %I:%M %p')}, table {table.label}"
            ),
        }

    if name == "cancel_reservation":
        day = dt.datetime.strptime(args["date"], "%Y-%m-%d").date()
        res = (
            db.query(Reservation)
            .filter(
                Reservation.phone_number == args["phone_number"],
                Reservation.status == ReservationStatus.confirmed,
            )
            .all()
        )
        match = next((r for r in res if r.reservation_time.date() == day), None)
        if not match:
            return {"success": False, "reason": "No matching reservation found."}
        match.status = ReservationStatus.cancelled
        db.commit()
        return {"success": True}

    if name == "add_item_to_order":
        item = (
            db.query(MenuItem)
            .filter(MenuItem.name.ilike(f"%{args['item_name']}%"), MenuItem.is_available.is_(True))
            .first()
        )
        if not item:
            return {"success": False, "reason": f"'{args['item_name']}' not found on the menu."}
        pending = _pending_orders.setdefault(session_id, [])
        pending.append(
            {
                "menu_item_id": item.id,
                "name": item.name,
                "quantity": int(args.get("quantity", 1)),
                "unit_price": item.price,
                "special_instructions": args.get("special_instructions", ""),
            }
        )
        running_total = sum(i["unit_price"] * i["quantity"] for i in pending)
        return {"success": True, "current_order": pending, "running_total": round(running_total, 2)}

    if name == "place_order":
        pending = _pending_orders.get(session_id, [])
        if not pending:
            return {"success": False, "reason": "No items have been added to the order yet."}
        order = Order(
            customer_name=args["customer_name"],
            phone_number=args["phone_number"],
            order_type=args.get("order_type", "pickup"),
            status=OrderStatus.placed,
            total_price=round(sum(i["unit_price"] * i["quantity"] for i in pending), 2),
        )
        db.add(order)
        db.flush()
        for i in pending:
            db.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=i["menu_item_id"],
                    menu_item_name=i["name"],
                    quantity=i["quantity"],
                    unit_price=i["unit_price"],
                    special_instructions=i["special_instructions"],
                )
            )
        db.commit()
        _pending_orders.pop(session_id, None)
        return {
            "success": True,
            "order_id": order.id,
            "total_price": order.total_price,
            "estimated_ready_minutes": 25,
        }

    if name == "transfer_to_human":
        log = db.query(CallLog).filter(CallLog.id == session_id).first()
        if log:
            log.escalated = True
            db.commit()
        return {"success": True, "message": "Transferring to a staff member now."}

    return {"success": False, "reason": f"Unknown tool: {name}"}


def _parse_dt(date_str: str, time_str: str) -> dt.datetime:
    return dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def _find_available_table(db: Session, party_size: int, when: dt.datetime) -> DiningTable | None:
    """
    Simple availability check: a table is free if its seats >= party_size
    and it has no confirmed reservation within a 90-minute turnover window
    of the requested time. Good enough for a single-location restaurant;
    swap for a real POS/reservation system call for production scale.
    """
    window_start = when - dt.timedelta(minutes=90)
    window_end = when + dt.timedelta(minutes=90)

    candidates = (
        db.query(DiningTable)
        .filter(DiningTable.seats >= party_size)
        .order_by(DiningTable.seats.asc())
        .all()
    )
    for table in candidates:
        clash = (
            db.query(Reservation)
            .filter(
                Reservation.table_id == table.id,
                Reservation.status == ReservationStatus.confirmed,
                Reservation.reservation_time > window_start,
                Reservation.reservation_time < window_end,
            )
            .first()
        )
        if not clash:
            return table
    return None
