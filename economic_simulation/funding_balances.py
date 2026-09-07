"""Read-only cash balances for controlled funding accounts."""
from .business_views import entity_names


def account_balances(world):
    # Reserved project money, receivables and credit are separate ledger accounts.
    # This is cash on hand, not permission to spend it past existing guardrails.
    from .application import money
    return {entity: dict(name=name, cash=world.cash(entity), label=money(world.cash(entity)))
            for entity, name in entity_names(world).items()}
