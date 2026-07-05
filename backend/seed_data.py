"""
Populates a fresh database with a sample menu and dining tables so the agent
has something real to talk about out of the box. Run once:

    python seed_data.py

Replace SAMPLE_MENU / SAMPLE_TABLES with your actual restaurant's data, or
write a small script that imports from your POS export (CSV/JSON) instead.
"""
from db import DiningTable, MenuItem, SessionLocal, init_db

SAMPLE_MENU = [
    dict(name="Bruschetta", category="appetizer", price=8.50,
         description="Grilled bread, tomato, basil, garlic",
         is_vegetarian=True, is_vegan=True),
    dict(name="Calamari Fritti", category="appetizer", price=12.00,
         description="Crispy fried squid, marinara sauce",
         contains_allergens="shellfish,gluten"),
    dict(name="Margherita Pizza", category="main", price=14.00,
         description="San Marzano tomato, fresh mozzarella, basil",
         contains_allergens="dairy,gluten", is_vegetarian=True),
    dict(name="Grilled Salmon", category="main", price=24.00,
         description="Atlantic salmon, lemon butter, seasonal greens",
         contains_allergens="fish"),
    dict(name="Chicken Parmesan", category="main", price=19.00,
         description="Breaded chicken breast, marinara, mozzarella, spaghetti",
         contains_allergens="dairy,gluten"),
    dict(name="Mushroom Risotto", category="main", price=17.00,
         description="Arborio rice, wild mushrooms, parmesan",
         contains_allergens="dairy", is_vegetarian=True),
    dict(name="Tiramisu", category="dessert", price=8.00,
         description="Espresso-soaked ladyfingers, mascarpone",
         contains_allergens="dairy,eggs,gluten"),
    dict(name="Panna Cotta", category="dessert", price=7.50,
         description="Vanilla bean cream, seasonal berry compote",
         contains_allergens="dairy", is_vegetarian=True),
    dict(name="House Red Wine (glass)", category="drink", price=9.00,
         description="Sangiovese blend"),
    dict(name="Sparkling Water", category="drink", price=3.50,
         is_vegan=True),
]

SAMPLE_TABLES = [
    dict(label="T1", seats=2),
    dict(label="T2", seats=2),
    dict(label="T3", seats=4),
    dict(label="T4", seats=4),
    dict(label="T5", seats=4),
    dict(label="T6", seats=6),
    dict(label="Patio 1", seats=4),
    dict(label="Patio 2", seats=6),
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        if db.query(MenuItem).count() == 0:
            db.bulk_save_objects([MenuItem(**item) for item in SAMPLE_MENU])
            print(f"Seeded {len(SAMPLE_MENU)} menu items.")
        else:
            print("Menu already has data, skipping.")

        if db.query(DiningTable).count() == 0:
            db.bulk_save_objects([DiningTable(**t) for t in SAMPLE_TABLES])
            print(f"Seeded {len(SAMPLE_TABLES)} tables.")
        else:
            print("Tables already have data, skipping.")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
