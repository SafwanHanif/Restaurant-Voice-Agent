"""
Gemini function declarations + a dispatcher that routes tool calls to service methods.

Each tool declaration follows the Gemini Live API Tool schema format.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ReservationCreate, OrderCreate, OrderItemCreate
from app.services import reservations as res_service
from app.services import menu as menu_service
from app.services import ordering as order_service

# ─── Tool Declarations (sent to Gemini at session start) ───────

TOOL_DECLARATIONS = [
    {
        "name": "check_availability",
        "description": "Check if tables are available for a given date, time, and party size. Returns available table options.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Reservation date in YYYY-MM-DD format"},
                "time": {"type": "string", "description": "Reservation time in HH:MM format (24h)"},
                "party_size": {"type": "integer", "description": "Number of guests"},
            },
            "required": ["date", "time", "party_size"],
        },
    },
    {
        "name": "create_reservation",
        "description": "Book a table reservation for a customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Full name of the customer"},
                "phone": {"type": "string", "description": "Customer phone number"},
                "email": {"type": "string", "description": "Customer email address (optional)"},
                "party_size": {"type": "integer", "description": "Number of guests"},
                "date": {"type": "string", "description": "Reservation date in YYYY-MM-DD format"},
                "time": {"type": "string", "description": "Reservation time in HH:MM format (24h)"},
                "special_requests": {"type": "string", "description": "Any special requests (allergies, celebrations, seating preferences)", "optional": True},
            },
            "required": ["customer_name", "phone", "party_size", "date", "time"],
        },
    },
    {
        "name": "cancel_reservation",
        "description": "Cancel an existing reservation by customer name and phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Name on the reservation"},
                "phone": {"type": "string", "description": "Phone number used for the reservation"},
                "date": {"type": "string", "description": "Reservation date in YYYY-MM-DD (optional)", "optional": True},
            },
            "required": ["customer_name", "phone"],
        },
    },
    {
        "name": "get_menu_item",
        "description": "Look up a menu item's details including price, ingredients, allergens, and dietary info.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Menu item name (partial match OK)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_menu_by_category",
        "description": "Get all menu items in a given category.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["appetizer", "main_course", "pasta", "pizza", "dessert", "beverage", "side"],
                    "description": "Menu category to browse",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "get_available_categories",
        "description": "Get a list of all menu categories that have available items. Use this when the customer asks 'what do you have' or 'what's on the menu'.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "find_safe_items",
        "description": "Find menu items that are safe given dietary restrictions or allergies.",
        "parameters": {
            "type": "object",
            "properties": {
                "allergen": {"type": "string", "description": "Allergen to exclude (e.g., 'peanuts', 'dairy', 'gluten')", "optional": True},
                "vegetarian": {"type": "boolean", "description": "Filter for vegetarian items", "optional": True},
                "vegan": {"type": "boolean", "description": "Filter for vegan items", "optional": True},
                "gluten_free": {"type": "boolean", "description": "Filter for gluten-free items", "optional": True},
            },
            "required": [],
        },
    },
    {
        "name": "get_restaurant_hours",
        "description": "Get the restaurant's opening hours. Call this when asked about when the restaurant is open or closed.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "transfer_to_human",
        "description": "Transfer the call to a human manager or staff member. Use for complaints, large party inquiries (8+), anything you're unsure about, or when the customer explicitly asks to speak to a person.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why this call needs a human"},
            },
            "required": ["reason"],
        },
    },
]

# ─── Restaurant Info (for system prompt context) ────────────────

RESTAURANT_HOURS = {
    "Monday": "11:00 AM — 10:00 PM",
    "Tuesday": "11:00 AM — 10:00 PM",
    "Wednesday": "11:00 AM — 10:00 PM",
    "Thursday": "11:00 AM — 10:00 PM",
    "Friday": "11:00 AM — 11:00 PM",
    "Saturday": "10:00 AM — 11:00 PM",
    "Sunday": "10:00 AM — 9:00 PM",
}

CATEGORY_TO_EMOJI = {
    "appetizer": "🧆 Appetizers",
    "main_course": "🍽️ Main Courses",
    "pasta": "🍝 Pasta",
    "pizza": "🍕 Pizza",
    "dessert": "🍰 Desserts",
    "beverage": "🥤 Beverages",
    "side": "🥗 Sides",
}


# ─── Tool Dispatcher ────────────────────────────────────────────

def format_table_list(tables: list) -> str:
    """Format table options for Gemini's response context."""
    parts = []
    for t in tables:
        loc = f" ({t.location})" if t.location else ""
        parts.append(f"Table #{t.table_number} — seats {t.capacity}{loc}")
    return "; ".join(parts) if parts else "No tables available"


async def handle_tool_call(
    session: AsyncSession,
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """
    Route a Gemini tool call to the correct service and return the result.
    This is the core dispatch function that bridges Gemini → FastAPI logic.
    """
    from datetime import date, time

    from app.models import MenuCategory

    if tool_name == "check_availability":
        res_date = date.fromisoformat(args["date"])
        res_time = time.fromisoformat(args["time"])
        available, tables = await res_service.check_table_availability(
            session, res_date, res_time, args["party_size"]
        )
        if available:
            return {
                "available": True,
                "message": f"We have tables available: {format_table_list(tables)}",
                "tables": [{"table_number": t.table_number, "capacity": t.capacity, "location": t.location} for t in tables],
            }
        return {"available": False, "message": "Sorry, no tables are available at that time."}

    elif tool_name == "create_reservation":
        res_data = ReservationCreate(
            customer_name=args["customer_name"],
            phone=args["phone"],
            email=args.get("email"),
            party_size=args["party_size"],
            reservation_date=date.fromisoformat(args["date"]),
            reservation_time=time.fromisoformat(args["time"]),
            special_requests=args.get("special_requests"),
        )
        reservation = await res_service.create_reservation(session, res_data)
        return {
            "success": True,
            "reservation_id": reservation.id,
            "message": f"Reservation confirmed for {reservation.customer_name}, {reservation.party_size} guests at {reservation.reservation_time} on {reservation.reservation_date}.",
        }

    elif tool_name == "cancel_reservation":
        res_date = date.fromisoformat(args["date"]) if args.get("date") else None
        cancelled = await res_service.cancel_reservation(
            session, args["customer_name"], args["phone"], res_date=res_date
        )
        if cancelled:
            return {"success": True, "message": f"Your reservation has been cancelled."}
        return {"success": False, "message": "No matching reservation was found to cancel. Please check the name and phone number."}

    elif tool_name == "get_menu_item":
        item = await menu_service.get_menu_item(session, name=args["name"])
        if item:
            return {
                "found": True,
                "name": item.name,
                "price": float(item.price),
                "description": item.description or "",
                "ingredients": item.ingredients or "",
                "allergens": item.allergens or "None listed",
                "is_spicy": item.is_spicy,
                "is_vegetarian": item.is_vegetarian,
                "is_vegan": item.is_vegan,
                "is_gluten_free": item.is_gluten_free,
                "available": item.is_available,
            }
        return {"found": False, "message": f"I couldn't find '{args['name']}' on the menu."}

    elif tool_name == "get_menu_by_category":
        category = MenuCategory(args["category"])
        items = await menu_service.get_menu_by_category(session, category)
        if items:
            return {
                "category": args["category"],
                "items": [
                    {
                        "name": i.name,
                        "price": float(i.price),
                        "description": i.description or "",
                        "available": i.is_available,
                    }
                    for i in items
                ],
            }
        return {"category": args["category"], "items": [], "message": f"We don't have any items in the {args['category']} category right now."}

    elif tool_name == "get_available_categories":
        from app.models import MenuItem
        from sqlalchemy import select, func

        result = await session.execute(
            select(MenuItem.category).where(MenuItem.is_available == True).distinct()  # noqa: E712
        )
        categories = [row[0].value for row in result.all()]
        return {
            "categories": categories,
            "labels": {c: CATEGORY_TO_EMOJI.get(c, c) for c in categories},
        }

    elif tool_name == "find_safe_items":
        items = await menu_service.find_safe_menu_items(
            session,
            allergen=args.get("allergen"),
            vegetarian=args.get("vegetarian", False),
            vegan=args.get("vegan", False),
            gluten_free=args.get("gluten_free", False),
        )
        return {
            "found": len(items) > 0,
            "items": [
                {
                    "name": i.name,
                    "price": float(i.price),
                    "description": i.description or "",
                    "allergens": i.allergens or "None listed",
                }
                for i in items
            ],
        }

    elif tool_name == "get_restaurant_hours":
        return {"hours": RESTAURANT_HOURS}

    elif tool_name == "transfer_to_human":
        # Signal to the bridge layer — actual transfer happens in twilio_webhooks.py
        return {
            "transfer": True,
            "reason": args.get("reason", "Customer requested to speak to a person"),
        }

    return {"error": f"Unknown tool: {tool_name}"}
