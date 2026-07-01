from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItem, MenuCategory


async def get_menu_item(
    session: AsyncSession,
    item_id: int | None = None,
    name: str | None = None,
) -> MenuItem | None:
    """Lookup a menu item by ID or name (case-insensitive partial match)."""
    if item_id:
        result = await session.execute(
            select(MenuItem).where(MenuItem.id == item_id)
        )
        return result.scalar_one_or_none()

    if name:
        result = await session.execute(
            select(MenuItem).where(MenuItem.name.ilike(f"%{name}%"))
        )
        return result.scalar_one_or_none()

    return None


async def get_menu_by_category(
    session: AsyncSession,
    category: MenuCategory | None = None,
) -> list[MenuItem]:
    """Get all available menu items, optionally filtered by category."""
    stmt = select(MenuItem).where(MenuItem.is_available == True)  # noqa: E712
    if category:
        stmt = stmt.where(MenuItem.category == category)
    stmt = stmt.order_by(MenuItem.category, MenuItem.name)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_safe_menu_items(
    session: AsyncSession,
    allergen: str | None = None,
    vegetarian: bool = False,
    vegan: bool = False,
    gluten_free: bool = False,
) -> list[MenuItem]:
    """Find menu items matching dietary preferences."""
    stmt = select(MenuItem).where(MenuItem.is_available == True)  # noqa: E712

    if allergen:
        # Exclude items that contain the allergen
        stmt = stmt.where(
            ~MenuItem.allergens.ilike(f"%{allergen}%")
        )
    if vegetarian:
        stmt = stmt.where(MenuItem.is_vegetarian == True)  # noqa: E712
    if vegan:
        stmt = stmt.where(MenuItem.is_vegan == True)  # noqa: E712
    if gluten_free:
        stmt = stmt.where(MenuItem.is_gluten_free == True)  # noqa: E712

    stmt = stmt.order_by(MenuItem.category, MenuItem.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())
