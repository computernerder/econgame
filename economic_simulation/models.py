"""Starter domain models. All money is stored as whole dollars for now."""

from dataclasses import dataclass, field


@dataclass
class Employee:
    name: str
    monthly_salary: int


@dataclass
class Property:
    name: str
    purchase_price: int
    monthly_upkeep: int


@dataclass
class Business:
    name: str
    location: Property
    monthly_revenue: int
    employees: list[Employee] = field(default_factory=list)

    @property
    def monthly_profit(self) -> int:
        payroll = sum(employee.monthly_salary for employee in self.employees)
        return self.monthly_revenue - payroll - self.location.monthly_upkeep


@dataclass
class Simulation:
    cash: int = 100_000
    month: int = 0
    businesses: list[Business] = field(default_factory=list)

    def advance_month(self) -> int:
        profit = sum(business.monthly_profit for business in self.businesses)
        self.cash += profit
        self.month += 1
        return profit
