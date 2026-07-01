from datetime import date, time, timedelta, datetime
from decimal import Decimal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Reservation, RestaurantTable, ReservationStatus
from app.schemas import ReservationCreate


async def check_table_availability(
    session: AsyncSession,
    res_date: date,
    res_time: time,
    party_size: int,
) -> tuple[bool, list[RestaurantTable]]:
    """
    Check if any table can accommodate the party at the given date/time.
    Returns (available, list_of_matching_tables).
    """
    # Find tables that can seat the party
    suitable_tables = await session.execute(
        select(RestaurantTable).where(
            RestaurantTable.capacity >= party_size,
            RestaurantTable.is_available == True,  # noqa: E712
        ).order_by(RestaurantTable.capacity)
    )
    suitable_tables = suitable_tables.scalars().all()

    if not suitable_tables:
        return False, []

    # Build time window: 1.5 hour slots
    window_start = datetime.combine(res_date, res_time) - timedelta(minutes=45)
    window_end = datetime.combine(res_date, res_time) + timedelta(minutes=45)
    window_start_t = window_start.time()
    window_end_t = window_end.time()

    # For each suitable table, check if it's already booked
    available_tables = []
    for table in suitable_tables:
        conflicting = await session.execute(
            select(Reservation).where(
                Reservation.table_id == table.id,
                Reservation.reservation_date == res_date,
                Reservation.status.in_([ReservationStatus.confirmed]),
                Reservation.reservation_time >= window_start_t,
                Reservation.reservation_time <= window_end_t,
            )
        )
        if not conflicting.scalars().first():
            available_tables.append(table)

    return len(available_tables) > 0, available_tables


async def create_reservation(
    session: AsyncSession,
    data: ReservationCreate,
    table: RestaurantTable | None = None,
) -> Reservation:
    """Create a new reservation, optionally assigning a specific table."""
    reservation = Reservation(
        customer_name=data.customer_name,
        phone=data.phone,
        email=data.email,
        party_size=data.party_size,
        reservation_date=data.reservation_date,
        reservation_time=data.reservation_time,
        special_requests=data.special_requests,
        table_id=table.id if table else None,
        status=ReservationStatus.confirmed,
    )
    session.add(reservation)
    await session.commit()
    await session.refresh(reservation)
    return reservation


async def cancel_reservation(
    session: AsyncSession,
    customer_name: str,
    phone: str,
    res_date: date | None = None,
    res_time: time | None = None,
) -> Reservation | None:
    """Cancel a reservation matching the given info. Returns the cancelled reservation or None."""
    stmt = select(Reservation).where(
        Reservation.customer_name.ilike(customer_name),
        Reservation.phone == phone,
        Reservation.status == ReservationStatus.confirmed,
    )
    if res_date:
        stmt = stmt.where(Reservation.reservation_date == res_date)
    if res_time:
        stmt = stmt.where(Reservation.reservation_time == res_time)

    result = await session.execute(stmt)
    reservation = result.scalar_one_or_none()

    if reservation:
        reservation.status = ReservationStatus.cancelled
        await session.commit()
        await session.refresh(reservation)

    return reservation


async def get_reservations_for_date(
    session: AsyncSession,
    res_date: date,
) -> list[Reservation]:
    """Get all reservations for a given date."""
    result = await session.execute(
        select(Reservation).where(
            Reservation.reservation_date == res_date,
            Reservation.status.in_([ReservationStatus.confirmed, ReservationStatus.completed]),
        ).order_by(Reservation.reservation_time)
    )
    return list(result.scalars().all())
