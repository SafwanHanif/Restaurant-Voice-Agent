from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItem, Order, OrderItem, OrderStatus
from app.schemas import OrderCreate


async def create_order(
    session: AsyncSession,
    data: OrderCreate,
) -> Order:
    """Create a new order with items. Calculates total from menu prices."""
    order = Order(
        customer_name=data.customer_name,
        phone=data.phone,
        notes=data.notes,
        status=OrderStatus.pending,
    )
    session.add(order)
    await session.flush()  # get order.id

    total = Decimal("0.00")
    items_list = []

    for item_data in data.items:
        # Get current menu price
        result = await session.execute(
            select(MenuItem).where(MenuItem.id == item_data.menu_item_id)
        )
        menu_item = result.scalar_one_or_none()

        if not menu_item or not menu_item.is_available:
            continue

        unit_price = menu_item.price
        line_total = unit_price * item_data.quantity
        total += line_total

        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=item_data.menu_item_id,
            quantity=item_data.quantity,
            unit_price=unit_price,
            special_instructions=item_data.special_instructions,
        )
        session.add(order_item)
        items_list.append(order_item)

    order.total = total
    await session.commit()
    await session.refresh(order)
    return order


async def get_order(
    session: AsyncSession,
    order_id: str,
) -> Order | None:
    """Look up an order by its ID."""
    result = await session.execute(
        select(Order).where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def cancel_order(
    session: AsyncSession,
    order_id: str,
) -> Order | None:
    """Cancel an order if it's still pending."""
    order = await get_order(session, order_id)
    if order and order.status == OrderStatus.pending:
        order.status = OrderStatus.cancelled
        await session.commit()
        await session.refresh(order)
    return order
