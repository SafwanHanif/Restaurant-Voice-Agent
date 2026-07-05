"""
WebSocket endpoint for the web mic widget (frontend/index.html).

Simpler than the Twilio bridge: the browser already sends 16-bit PCM at
16kHz (resampled client-side, see index.html), so no mulaw/rate conversion
is needed on the way in. Gemini's 24kHz PCM16 output is sent back as-is;
the browser's AudioContext plays it directly at 24kHz.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import uuid
from collections import Counter

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from db import MenuItem, Order, OrderItem, OrderStatus, get_db
from gemini_session import GeminiVoiceSession

logger = logging.getLogger("voice_agent")
router = APIRouter()


def _fmt_menu(m: MenuItem) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "category": m.category,
        "description": m.description,
        "price": m.price,
        "available": m.is_available,
        "vegetarian": m.is_vegetarian,
        "vegan": m.is_vegan,
        "allergens": m.contains_allergens,
    }


@router.get("/api/menu")
def get_menu():
    """Return the full menu grouped by category."""
    db = get_db()
    try:
        items = db.query(MenuItem).order_by(MenuItem.category, MenuItem.name).all()
        grouped: dict[str, list[dict]] = {}
        for item in items:
            grouped.setdefault(item.category.capitalize(), []).append(_fmt_menu(item))
        return {"categories": grouped}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dashboard pages
# ---------------------------------------------------------------------------


@router.get("/admin")
def admin_dashboard():
    """Kitchen dashboard — live orders in lane view."""
    return FileResponse("../frontend/admin.html")


@router.get("/order-lookup")
def order_lookup_page():
    """Customer order lookup page."""
    return FileResponse("../frontend/order-lookup.html")


@router.get("/analytics")
def analytics_page():
    """Analytics dashboard."""
    return FileResponse("../frontend/analytics.html")


@router.get("/order")
def order_page():
    """Online ordering page."""
    return FileResponse("../frontend/order.html")


# ---------------------------------------------------------------------------
# Admin API — kitchen dashboard
# ---------------------------------------------------------------------------


@router.get("/api/admin/orders")
def get_admin_orders():
    """All orders with items, newest first. Kitchen dashboard polls this."""
    db = get_db()
    try:
        orders = db.query(Order).order_by(Order.created_at.desc()).all()
        return {
            "orders": [
                {
                    "id": o.id,
                    "short_id": o.id[-6:],
                    "customer_name": o.customer_name,
                    "phone_number": o.phone_number,
                    "order_type": o.order_type,
                    "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                    "total_price": o.total_price,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                    "items": [
                        {
                            "name": i.menu_item_name,
                            "quantity": i.quantity,
                            "unit_price": i.unit_price,
                            "special_instructions": i.special_instructions,
                        }
                        for i in o.items
                    ],
                }
                for o in orders
            ]
        }
    finally:
        db.close()


@router.post("/api/admin/orders/{order_id}/advance")
def advance_order_status(order_id: str):
    """
    Advance an order to its next status in the kitchen flow:
    placed → preparing → ready → completed
    """
    db = get_db()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"success": False, "reason": "Order not found"}

        flow = [OrderStatus.placed, OrderStatus.preparing, OrderStatus.ready, OrderStatus.completed]
        try:
            idx = flow.index(order.status)
        except ValueError:
            return {"success": False, "reason": f"Order is in '{order.status}' — cannot advance further"}

        if idx >= len(flow) - 1:
            return {"success": False, "reason": "Order is already completed"}

        order.status = flow[idx + 1]
        db.commit()
        return {"success": True, "new_status": order.status.value}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Admin API — order editing
# ---------------------------------------------------------------------------


@router.patch("/api/admin/orders/{order_id}")
def update_order(order_id: str, body: dict):
    """Update an order's status and/or notes. Supports any status transition."""
    db = get_db()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"success": False, "reason": "Order not found"}

        new_status = body.get("status")
        if new_status:
            try:
                order.status = OrderStatus(new_status)
            except ValueError:
                return {"success": False, "reason": f"Invalid status: {new_status}"}

        if "notes" in body:
            order.notes = body["notes"]

        db.commit()
        return {"success": True, "status": order.status.value}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Analytics API
# ---------------------------------------------------------------------------


@router.get("/api/admin/analytics")
def get_analytics():
    """Aggregated order analytics for the dashboard."""
    db = get_db()
    try:
        orders = db.query(Order).all()
        now = dt.datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - dt.timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        def _revenue(order_list):
            return round(sum(o.total_price for o in order_list if o.status != OrderStatus.cancelled), 2)

        today_orders = [o for o in orders if o.created_at and o.created_at >= today_start]
        week_orders = [o for o in orders if o.created_at and o.created_at >= week_start]

        # Daily breakdown (last 7 days)
        daily_orders = []
        for i in range(6, -1, -1):
            day = today_start - dt.timedelta(days=i)
            next_day = day + dt.timedelta(days=1)
            day_orders = [o for o in orders if o.created_at and day <= o.created_at < next_day]
            daily_orders.append({
                "date": day.strftime("%a"),
                "orders": len(day_orders),
                "revenue": _revenue(day_orders),
            })

        # Top items
        item_counter: Counter = Counter()
        for o in orders:
            for i in o.items:
                item_counter[i.menu_item_name] += i.quantity
        top_items = [{"name": n, "count": c} for n, c in item_counter.most_common(10)]

        # Peak hours
        hourly = Counter()
        for o in orders:
            if o.created_at:
                hourly[o.created_at.hour] += 1
        peak_hours = sorted(
            ({"hour": h, "orders": c} for h, c in hourly.items()), key=lambda x: x["hour"]
        )

        # Status breakdown
        status_counts = Counter(o.status.value if hasattr(o.status, "value") else str(o.status) for o in orders)

        return {
            "total_orders": len(orders),
            "total_revenue": _revenue(orders),
            "today_orders": len(today_orders),
            "today_revenue": _revenue(today_orders),
            "week_orders": len(week_orders),
            "week_revenue": _revenue(week_orders),
            "daily_orders": daily_orders,
            "top_items": top_items,
            "peak_hours": peak_hours,
            "status_breakdown": dict(status_counts),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Customer order lookup API
# ---------------------------------------------------------------------------


@router.get("/api/orders/lookup")
def lookup_orders(phone: str = "", order_id: str = ""):
    """Lookup orders by phone number or order ID."""
    if not phone and not order_id:
        return {"orders": []}
    db = get_db()
    try:
        q = db.query(Order)
        if phone:
            q = q.filter(Order.phone_number == phone)
        else:
            q = q.filter(Order.id == order_id)
        orders = q.order_by(Order.created_at.desc()).all()
        return {
            "orders": [
                {
                    "id": o.id,
                    "short_id": o.id[-6:],
                    "customer_name": o.customer_name,
                    "order_type": o.order_type,
                    "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                    "total_price": o.total_price,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                    "items": [
                        {
                            "name": i.menu_item_name,
                            "quantity": i.quantity,
                            "unit_price": i.unit_price,
                        }
                        for i in o.items
                    ],
                }
                for o in orders
            ]
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Online ordering API
# ---------------------------------------------------------------------------


class _OrderItemIn(BaseModel):
    menu_item_id: str
    quantity: int = 1


class _OrderCreateIn(BaseModel):
    customer_name: str
    phone_number: str
    order_type: str = "pickup"
    items: list[_OrderItemIn]


@router.post("/api/orders")
def create_order(body: _OrderCreateIn):
    """Create an order from the online ordering page."""
    db = get_db()
    try:
        order = Order(
            customer_name=body.customer_name,
            phone_number=body.phone_number,
            order_type=body.order_type,
            status=OrderStatus.placed,
            total_price=0.0,
        )
        db.add(order)
        db.flush()

        total = 0.0
        for item in body.items:
            menu_item = db.query(MenuItem).filter(MenuItem.id == item.menu_item_id).first()
            if not menu_item:
                continue
            db.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=menu_item.id,
                    menu_item_name=menu_item.name,
                    quantity=item.quantity,
                    unit_price=menu_item.price,
                )
            )
            total += menu_item.price * item.quantity

        order.total_price = round(total, 2)
        db.commit()

        return {
            "success": True,
            "order_id": order.id,
            "short_id": order.id[-6:],
            "total_price": order.total_price,
            "estimated_ready_minutes": 25,
        }
    finally:
        db.close()


@router.websocket("/ws/web-call")
async def web_call(websocket: WebSocket):
    await websocket.accept()
    session_id = uuid.uuid4().hex[:12]
    logger.info("[%s] web call started", session_id)

    audio_in_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def send_to_browser(pcm24k_bytes: bytes):
        await websocket.send_bytes(pcm24k_bytes)

    async def send_event(event: dict):
        await websocket.send_text(json.dumps(event))

    session = GeminiVoiceSession(session_id, channel="web")
    gemini_task = asyncio.create_task(session.run(send_to_browser, audio_in_queue, send_event))

    try:
        while True:
            data = await websocket.receive_bytes()
            await audio_in_queue.put(data)
    except WebSocketDisconnect:
        logger.info("[%s] web call ended", session_id)
    finally:
        await audio_in_queue.put(None)
        await gemini_task
