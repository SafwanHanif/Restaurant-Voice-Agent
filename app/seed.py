"""
Seed data for the restaurant database.
Run with: python -m app.seed
"""

import asyncio
from datetime import date, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, init_db, close_db
from app.models import MenuItem, MenuCategory, RestaurantTable, Reservation, ReservationStatus


SAMPLE_TABLES = [
    # Small tables (2-top)
    RestaurantTable(table_number=1, capacity=2, location="window"),
    RestaurantTable(table_number=2, capacity=2, location="window"),
    RestaurantTable(table_number=3, capacity=2, location="patio"),
    RestaurantTable(table_number=4, capacity=2, location="patio"),
    RestaurantTable(table_number=5, capacity=2, location="bar"),
    RestaurantTable(table_number=6, capacity=2, location="bar"),
    # Medium tables (4-top)
    RestaurantTable(table_number=7, capacity=4, location="main"),
    RestaurantTable(table_number=8, capacity=4, location="main"),
    RestaurantTable(table_number=9, capacity=4, location="window"),
    RestaurantTable(table_number=10, capacity=4, location="patio"),
    RestaurantTable(table_number=11, capacity=4, location="main"),
    # Large tables (6+)
    RestaurantTable(table_number=12, capacity=6, location="main"),
    RestaurantTable(table_number=13, capacity=6, location="patio"),
    RestaurantTable(table_number=14, capacity=8, location="main"),
    RestaurantTable(table_number=15, capacity=8, location="private"),
]


SAMPLE_MENU_ITEMS = [
    # ── Appetizers ──
    MenuItem(
        name="Bruschetta",
        description="Toasted ciabatta topped with fresh tomatoes, basil, and extra virgin olive oil",
        price=Decimal("12.00"),
        category=MenuCategory.appetizer,
        ingredients="Bread, Tomatoes, Basil, Olive Oil, Garlic",
        allergens="Gluten",
        is_vegetarian=True,
        is_vegan=True,
    ),
    MenuItem(
        name="Calamari Fritti",
        description="Crispy fried calamari served with marinara sauce and lemon",
        price=Decimal("14.00"),
        category=MenuCategory.appetizer,
        ingredients="Squid, Flour, Eggs, Marinara Sauce",
        allergens="Shellfish, Gluten, Eggs",
    ),
    MenuItem(
        name="Caprese Salad",
        description="Fresh mozzarella, vine-ripened tomatoes, basil, and balsamic reduction",
        price=Decimal("13.00"),
        category=MenuCategory.appetizer,
        ingredients="Mozzarella, Tomatoes, Basil, Balsamic Vinegar, Olive Oil",
        allergens="Dairy",
        is_vegetarian=True,
        is_gluten_free=True,
    ),
    # ── Pasta ──
    MenuItem(
        name="Spaghetti Carbonara",
        description="Classic Roman pasta with eggs, pecorino romano, guanciale, and black pepper",
        price=Decimal("18.00"),
        category=MenuCategory.pasta,
        ingredients="Spaghetti, Eggs, Pecorino Romano, Guanciale, Black Pepper",
        allergens="Gluten, Eggs, Dairy",
    ),
    MenuItem(
        name="Fettuccine Alfredo",
        description="Homemade fettuccine in a rich parmesan cream sauce",
        price=Decimal("17.00"),
        category=MenuCategory.pasta,
        ingredients="Fettuccine, Cream, Parmesan, Butter, Garlic",
        allergens="Gluten, Dairy",
        is_vegetarian=True,
    ),
    MenuItem(
        name="Penne Arrabbiata",
        description="Penne in a spicy tomato sauce with garlic and chili flakes",
        price=Decimal("15.00"),
        category=MenuCategory.pasta,
        ingredients="Penne, Tomatoes, Garlic, Chili Flakes, Olive Oil",
        allergens="Gluten",
        is_vegetarian=True,
        is_vegan=True,
        is_spicy=True,
    ),
    MenuItem(
        name="Lasagna Bolognese",
        description="Layers of pasta with slow-cooked meat ragu, béchamel, and parmesan",
        price=Decimal("20.00"),
        category=MenuCategory.pasta,
        ingredients="Pasta, Ground Beef, Tomatoes, Béchamel, Parmesan, Herbs",
        allergens="Gluten, Dairy, Eggs",
    ),
    # ── Pizza ──
    MenuItem(
        name="Margherita Pizza",
        description="San Marzano tomatoes, fresh mozzarella, basil, and olive oil",
        price=Decimal("16.00"),
        category=MenuCategory.pizza,
        ingredients="Pizza Dough, San Marzano Tomatoes, Mozzarella, Basil, Olive Oil",
        allergens="Gluten, Dairy",
        is_vegetarian=True,
    ),
    MenuItem(
        name="Pepperoni Pizza",
        description="Classic pepperoni with mozzarella and house-made tomato sauce",
        price=Decimal("17.00"),
        category=MenuCategory.pizza,
        ingredients="Pizza Dough, Pepperoni, Mozzarella, Tomato Sauce",
        allergens="Gluten, Dairy",
    ),
    MenuItem(
        name="Quattro Formaggi",
        description="Four-cheese pizza with mozzarella, gorgonzola, fontina, and parmesan",
        price=Decimal("19.00"),
        category=MenuCategory.pizza,
        ingredients="Pizza Dough, Mozzarella, Gorgonzola, Fontina, Parmesan, Cream",
        allergens="Gluten, Dairy",
        is_vegetarian=True,
    ),
    MenuItem(
        name="Prosciutto & Arugula Pizza",
        description="Thin crust topped with prosciutto, fresh arugula, and shaved parmesan",
        price=Decimal("20.00"),
        category=MenuCategory.pizza,
        ingredients="Pizza Dough, Prosciutto, Arugula, Parmesan, Olive Oil",
        allergens="Gluten, Dairy",
    ),
    # ── Main Courses ──
    MenuItem(
        name="Chicken Parmigiana",
        description="Breaded chicken breast topped with marinara and melted mozzarella, served with spaghetti",
        price=Decimal("22.00"),
        category=MenuCategory.main_course,
        ingredients="Chicken, Breadcrumbs, Eggs, Mozzarella, Marinara, Spaghetti",
        allergens="Gluten, Dairy, Eggs",
    ),
    MenuItem(
        name="Grilled Salmon",
        description="Atlantic salmon fillet with lemon butter sauce, roasted vegetables, and rice pilaf",
        price=Decimal("26.00"),
        category=MenuCategory.main_course,
        ingredients="Salmon, Lemon, Butter, Vegetables, Rice",
        allergens="Fish, Dairy",
        is_gluten_free=True,
    ),
    MenuItem(
        name="Eggplant Parmesan",
        description="Breaded eggplant layered with marinara, mozzarella, and basil",
        price=Decimal("19.00"),
        category=MenuCategory.main_course,
        ingredients="Eggplant, Breadcrumbs, Marinara, Mozzarella, Parmesan",
        allergens="Gluten, Dairy, Eggs",
        is_vegetarian=True,
    ),
    # ── Desserts ──
    MenuItem(
        name="Tiramisu",
        description="Classic Italian dessert with espresso-soaked ladyfingers and mascarpone cream",
        price=Decimal("10.00"),
        category=MenuCategory.dessert,
        ingredients="Ladyfingers, Mascarpone, Espresso, Cocoa, Eggs, Sugar",
        allergens="Gluten, Dairy, Eggs",
        is_vegetarian=True,
    ),
    MenuItem(
        name="Panna Cotta",
        description="Vanilla cream with mixed berry compote",
        price=Decimal("9.00"),
        category=MenuCategory.dessert,
        ingredients="Cream, Vanilla, Gelatin, Berries, Sugar",
        allergens="Dairy",
        is_vegetarian=True,
        is_gluten_free=True,
    ),
    MenuItem(
        name="Gelato (3 scoops)",
        description="Three scoops of house-made gelato — choose from vanilla, chocolate, strawberry, or pistachio",
        price=Decimal("8.00"),
        category=MenuCategory.dessert,
        ingredients="Milk, Sugar, Cream, Natural Flavors",
        allergens="Dairy",
        is_vegetarian=True,
        is_gluten_free=True,
    ),
    # ── Beverages ──
    MenuItem(
        name="Espresso",
        description="Single shot of house-roasted espresso",
        price=Decimal("3.50"),
        category=MenuCategory.beverage,
        ingredients="Coffee Beans",
        is_vegetarian=True,
        is_vegan=True,
        is_gluten_free=True,
    ),
    MenuItem(
        name="Cappuccino",
        description="Espresso with steamed milk foam",
        price=Decimal("4.50"),
        category=MenuCategory.beverage,
        ingredients="Espresso, Milk",
        allergens="Dairy",
        is_vegetarian=True,
        is_gluten_free=True,
    ),
    MenuItem(
        name="San Pellegrino Sparkling Water",
        description="750ml bottle of Italian sparkling mineral water",
        price=Decimal("5.00"),
        category=MenuCategory.beverage,
        ingredients="Sparkling Mineral Water",
        is_vegetarian=True,
        is_vegan=True,
        is_gluten_free=True,
    ),
    MenuItem(
        name="House Red Wine (Glass)",
        description="Glass of our house Chianti",
        price=Decimal("9.00"),
        category=MenuCategory.beverage,
        ingredients="Red Wine",
        is_vegetarian=True,
        is_vegan=True,
        is_gluten_free=True,
    ),
    # ── Sides ──
    MenuItem(
        name="Garlic Bread",
        description="Toasted ciabatta with garlic butter and herbs",
        price=Decimal("5.00"),
        category=MenuCategory.side,
        ingredients="Bread, Garlic Butter, Herbs",
        allergens="Gluten, Dairy",
        is_vegetarian=True,
    ),
    MenuItem(
        name="Roasted Vegetables",
        description="Seasonal vegetables roasted with olive oil and herbs",
        price=Decimal("6.00"),
        category=MenuCategory.side,
        ingredients="Seasonal Vegetables, Olive Oil, Herbs, Garlic",
        is_vegetarian=True,
        is_vegan=True,
        is_gluten_free=True,
    ),
]


SAMPLE_RESERVATIONS = [
    Reservation(
        customer_name="John Doe",
        phone="+15551234567",
        party_size=4,
        reservation_date=date(2026, 7, 1),
        reservation_time=time(19, 0),
        status=ReservationStatus.confirmed,
        table_id=7,
    ),
    Reservation(
        customer_name="Jane Smith",
        phone="+15559876543",
        party_size=2,
        reservation_date=date(2026, 7, 1),
        reservation_time=time(18, 30),
        status=ReservationStatus.confirmed,
        table_id=1,
    ),
    Reservation(
        customer_name="Bob Johnson",
        phone="+15555550000",
        party_size=6,
        reservation_date=date(2026, 7, 2),
        reservation_time=time(20, 0),
        status=ReservationStatus.confirmed,
        table_id=12,
    ),
]


async def seed_database():
    """Populate the database with sample data."""
    await init_db()

    async with async_session_factory() as session:
        # Check if data already exists
        existing_tables = await session.execute(select(RestaurantTable).limit(1))
        if existing_tables.scalar_one_or_none():
            print("Database already seeded — skipping.")
            return

        # Seed tables
        session.add_all(SAMPLE_TABLES)
        await session.flush()
        print(f"[OK] Seeded {len(SAMPLE_TABLES)} tables")

        # Seed menu items
        session.add_all(SAMPLE_MENU_ITEMS)
        await session.flush()
        print(f"[OK] Seeded {len(SAMPLE_MENU_ITEMS)} menu items")

        # Seed reservations
        session.add_all(SAMPLE_RESERVATIONS)
        await session.flush()
        print(f"[OK] Seeded {len(SAMPLE_RESERVATIONS)} reservations")

        await session.commit()

    print("\n[OK] Database seeded successfully!")
    print("Restaurant: Bella Italia")
    print("Tables: 15 (2-top to 8-top)")
    print(f"Menu items: {len(SAMPLE_MENU_ITEMS)} across 7 categories")
    print("Reservations: 3 sample bookings")


if __name__ == "__main__":
    asyncio.run(seed_database())
