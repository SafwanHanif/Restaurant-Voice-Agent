"""Initial migration: create restaurant tables

Revision ID: 001
Revises: None
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ──
    sa.Enum("confirmed", "cancelled", "completed", "no_show", name="reservationstatus").create(op.get_bind())
    sa.Enum("pending", "confirmed", "preparing", "ready", "delivered", "cancelled", name="orderstatus").create(op.get_bind())
    sa.Enum(
        "appetizer", "main_course", "pasta", "pizza", "dessert", "beverage", "side",
        name="menucategory",
    ).create(op.get_bind())

    # ── restaurant_tables ──
    op.create_table(
        "restaurant_tables",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("table_number", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("location", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_number"),
    )

    # ── reservations ──
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("reservation_date", sa.Date(), nullable=False),
        sa.Column("reservation_time", sa.Time(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("confirmed", "cancelled", "completed", "no_show", name="reservationstatus", create_type=False),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("restaurant_tables.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── menu_items ──
    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(8, 2), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM("appetizer", "main_course", "pasta", "pizza", "dessert", "beverage", "side", name="menucategory", create_type=False),
            nullable=False,
        ),
        sa.Column("ingredients", sa.Text(), nullable=True),
        sa.Column("allergens", sa.Text(), nullable=True),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_spicy", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_vegetarian", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_vegan", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_gluten_free", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── orders ──
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "confirmed", "preparing", "ready", "delivered", "cancelled", name="orderstatus", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("total", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("square_order_id", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── order_items ──
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("unit_price", sa.Numeric(8, 2), nullable=False),
        sa.Column("special_instructions", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("menu_items")
    op.drop_table("reservations")
    op.drop_table("restaurant_tables")

    sa.Enum(name="orderstatus").drop(op.get_bind())
    sa.Enum(name="reservationstatus").drop(op.get_bind())
    sa.Enum(name="menucategory").drop(op.get_bind())
