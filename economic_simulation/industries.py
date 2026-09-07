"""Shared operating capacity definitions used by the engine and hiring guide."""

# Qualified minutes required per sale in each of two overlapping roles.
SALES = {
    'boutique': ('salesperson', 12, 'stocker', 6, 'boutique_sales', 'fashion items sold'),
    'retail': ('cashier', 6, 'stocker', 60 / 18, 'retail_sales', 'items sold'),
    'restaurant': ('chef', 60 / 13, 'server', 4, 'meal_sales', 'meals served'),
    'gas_station': ('cashier', 0.75, 'attendant', 0.6, 'fuel_sales', 'gallons sold'),
    'grocery': ('cashier', 2, 'stocker', 60 / 45, 'grocery_sales', 'baskets sold'),
    'car_dealership': ('salesperson', 180, 'mechanic', 120, 'vehicle_sales', 'vehicles sold'),
}
PROJECTS = {
    'factory': ('machine_operator', 'production_worker', 50),
    'engineering': ('engineer', 'technician', 70),
    'trades': ('tradesperson', 'apprentice', 50),
    'construction': ('builder', 'laborer', 50),
}


def sales_capacity(industry, buckets):
    a, am, b, bm, _, _ = SALES[industry]
    if industry == 'car_dealership':
        # A sale spans multiple hours; both sales and preparation must be staffed.
        return int(sum(min(buckets[a][h] / am, buckets[b][h] / bm) for h in range(24)))
    return sum(min(int(buckets[a][h] / am + 1e-9), int(buckets[b][h] / bm + 1e-9)) for h in range(24))


def project_capacity(industry, minutes):
    lead, support, percent = PROJECTS[industry]
    # Apprentices and laborers need qualified supervision; technicians retain
    # the existing engineering behavior.
    extra = minutes[support] * percent // 100
    if industry != 'engineering':
        extra = min(extra, minutes[lead])
    return minutes[lead] + extra
