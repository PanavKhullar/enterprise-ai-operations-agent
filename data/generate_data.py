import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.database import engine, Base
from app.db.models import (
    Warehouse,
    Carrier,
    Order,
    Shipment,
    SLAEvent,
)


random.seed(42)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

NUM_ORDERS = 10000

REGIONS = [
    "North",
    "South",
    "East",
    "West",
]

WAREHOUSES = [
    ("WH_01", "Bangalore Warehouse", "South", 5000),
    ("WH_02", "Delhi Warehouse", "North", 6000),
    ("WH_03", "Mumbai Warehouse", "West", 4500),
    ("WH_04", "Kolkata Warehouse", "East", 4000),
    ("WH_05", "Hyderabad Warehouse", "South", 5500),
]

CARRIERS = [
    ("CAR_01", "FastTrack Logistics"),
    ("CAR_02", "BlueDart Express"),
    ("CAR_03", "Delhivery"),
    ("CAR_04", "Ecom Express"),
]


# --------------------------------------------------
# Utility functions
# --------------------------------------------------

def random_date(start_date, end_date):
    delta = end_date - start_date

    random_days = random.randint(0, delta.days)

    return start_date + timedelta(days=random_days)


# --------------------------------------------------
# Generate warehouses
# --------------------------------------------------

def generate_warehouses():

    warehouses = []

    for warehouse_id, name, region, capacity in WAREHOUSES:

        warehouses.append(
            Warehouse(
                warehouse_id=warehouse_id,
                name=name,
                region=region,
                capacity=capacity,
            )
        )

    return warehouses


# --------------------------------------------------
# Generate carriers
# --------------------------------------------------

def generate_carriers():

    carriers = []

    for carrier_id, name in CARRIERS:

        carriers.append(
            Carrier(
                carrier_id=carrier_id,
                name=name,
            )
        )

    return carriers


# --------------------------------------------------
# Generate orders
# --------------------------------------------------

def generate_orders(start_date, end_date):

    orders = []

    for i in range(NUM_ORDERS):

        order_id = f"ORD_{i + 1:06d}"

        warehouse_id, _, region, _ = random.choice(
            WAREHOUSES
        )

        created_at = random_date(
            start_date,
            end_date
        )

        # Normal promised delivery:
        # 2–5 days after order creation

        promised_at = created_at + timedelta(
            days=random.randint(2, 5)
        )

        orders.append(
            Order(
                order_id=order_id,
                warehouse_id=warehouse_id,
                region=region,
                created_at=created_at,
                promised_at=promised_at,
            )
        )

    return orders


# --------------------------------------------------
# Generate shipments
# --------------------------------------------------

def generate_shipments(orders, start_date):

    shipments = []

    for order in orders:

        shipment_id = f"SHP_{order.order_id[4:]}"

        carrier_id = random.choice(CARRIERS)[0]

        # Normal warehouse processing time
        processing_hours = random.randint(4, 24)

        shipped_at = order.created_at + timedelta(
            hours=processing_hours
        )

        # --------------------------------------------------
        # Hidden anomaly:
        #
        # WH_03 starts performing badly during the
        # most recent 30 days.
        # --------------------------------------------------

        recent_period = (
            order.created_at >=
            start_date + timedelta(days=150)
        )

        if (
            order.warehouse_id == "WH_03"
            and recent_period
        ):
            processing_hours += random.randint(12, 36)

            shipped_at = order.created_at + timedelta(
                hours=processing_hours
            )

        # --------------------------------------------------
        # Carrier anomaly:
        #
        # CAR_03 becomes slower recently.
        # --------------------------------------------------

        delivery_days = random.randint(1, 3)

        if (
            carrier_id == "CAR_03"
            and recent_period
        ):
            delivery_days += random.randint(1, 3)

        delivered_at = (
            shipped_at +
            timedelta(days=delivery_days)
        )

        shipments.append(
            Shipment(
                shipment_id=shipment_id,
                order_id=order.order_id,
                warehouse_id=order.warehouse_id,
                carrier_id=carrier_id,
                shipped_at=shipped_at,
                delivered_at=delivered_at,
            )
        )

    return shipments


# --------------------------------------------------
# Generate SLA events
# --------------------------------------------------

def generate_sla_events(orders, shipments):

    sla_events = []

    shipment_lookup = {
        shipment.order_id: shipment
        for shipment in shipments
    }

    for order in orders:

        shipment = shipment_lookup[order.order_id]

        event_id = f"SLA_{order.order_id[4:]}"

        expected_time = order.promised_at

        actual_time = shipment.delivered_at

        delay_seconds = (
            actual_time - expected_time
        ).total_seconds()

        delay_minutes = max(
            delay_seconds / 60,
            0
        )

        if delay_minutes > 0:

            event_type = "SLA_BREACH"

        else:

            event_type = "SLA_MET"

        sla_events.append(
            SLAEvent(
                event_id=event_id,
                order_id=order.order_id,
                warehouse_id=order.warehouse_id,
                event_type=event_type,
                expected_time=expected_time,
                actual_time=actual_time,
                delay_minutes=round(
                    delay_minutes,
                    2
                ),
                created_at=actual_time,
            )
        )

    return sla_events


# --------------------------------------------------
# Main
# --------------------------------------------------
def main():

    print("Creating database tables...")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    start_date = datetime.now() - timedelta(days=180)
    end_date = datetime.now()

    print("Generating warehouses...")
    warehouses = generate_warehouses()

    print("Generating carriers...")
    carriers = generate_carriers()

    print("Generating orders...")
    orders = generate_orders(
        start_date,
        end_date
    )

    print("Generating shipments...")
    shipments = generate_shipments(
        orders,
        start_date
    )

    print("Generating SLA events...")
    sla_events = generate_sla_events(
        orders,
        shipments
    )

    with Session(engine) as session:

        # ------------------------------------------
        # 1. Parent tables
        # ------------------------------------------

        print("Inserting warehouses...")
        session.add_all(warehouses)

        print("Inserting carriers...")
        session.add_all(carriers)

        session.commit()

        # ------------------------------------------
        # 2. Orders depend on warehouses
        # ------------------------------------------

        print("Inserting orders...")
        session.add_all(orders)

        session.commit()

        # ------------------------------------------
        # 3. Shipments depend on orders + warehouses
        # ------------------------------------------

        print("Inserting shipments...")
        session.add_all(shipments)

        session.commit()

        # ------------------------------------------
        # 4. SLA events depend on orders + warehouses
        # ------------------------------------------

        print("Inserting SLA events...")
        session.add_all(sla_events)

        session.commit()

    print()
    print("Data generation completed.")
    print(f"Warehouses : {len(warehouses)}")
    print(f"Carriers   : {len(carriers)}")
    print(f"Orders     : {len(orders)}")
    print(f"Shipments  : {len(shipments)}")
    print(f"SLA Events : {len(sla_events)}")



if __name__ == "__main__":
    main()