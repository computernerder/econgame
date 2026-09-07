"""Stable keyed uncertainty and versioned extension records."""
import hashlib


def stable_roll(world,key,maximum=100):
    return int.from_bytes(hashlib.sha256(f'{world.seed}:{key}'.encode()).digest()[:8],'big')%maximum
