"""Deterministic human names, independent of economic random streams."""
import hashlib
import re

FIRST = tuple('Alex Avery Bailey Cameron Casey Charlie Dakota Drew Elliot Emerson Finley Hayden Jamie Jordan Jules Kai Kendall Lane Logan Marley Morgan Parker Peyton Quinn Reese Riley Robin Rowan Sage Sam Sidney Skyler Taylor Adrian Amelia Aria Arthur Audrey Benjamin Blake Caleb Clara Daniel Elena Eli Elise Ethan Eva Felix Gabriel Grace Hannah Harper Hazel Henry Isaac Isla Ivy Jasper Jonah Joseph Julian Leah Leo Liam Lily Lucas Lucy Maya Miles Naomi Nathan Noah Nora Oliver Owen Paige Penelope Rachel Ruby Sadie Samuel Sarah Sebastian Sophia Stella Theo Thomas Violet Vivian Wesley William Zoe'.split())
LAST = tuple('Adams Allen Anderson Archer Bailey Baker Bennett Blake Brooks Brown Campbell Carter Chen Clarke Cole Collins Cooper Davis Dawson Diaz Ellis Evans Fisher Flores Ford Foster Fox Garcia Gray Green Griffin Hall Hamilton Harris Hayes Hill Howard Hughes Jackson James Jensen Johnson Jones Kelly Kim King Lane Lawson Lee Lewis Martin Mason Miller Mitchell Moore Morgan Morris Murphy Nelson Nguyen Ortiz Palmer Park Parker Patel Perry Peterson Phillips Porter Powell Price Reed Reyes Reynolds Rivera Roberts Robinson Ross Russell Sanders Scott Shaw Simmons Singh Smith Spencer Stone Sullivan Taylor Thomas Thompson Torres Turner Walker Ward Watson Wells West White Williams Wilson Wood Wright Young'.split())


def unique_name(world, identity, used=None):
    used = {p.name.casefold() for p in world.people} if used is None else used
    start = int.from_bytes(hashlib.sha256(f'{world.seed}:{identity}:name'.encode()).digest()[:8], 'big')
    size = len(FIRST)*len(LAST)
    for index in range(size*(len(FIRST)+1)):
        value = (start+index) % size
        first, last = FIRST[value//len(LAST)], LAST[value % len(LAST)]
        middle = '' if index < size else FIRST[(index//size-1) % len(FIRST)]+' '
        name = first+' '+middle+last
        if name.casefold() not in used:return name
    raise ValueError('The employee name catalog is exhausted.')


def migrate_names(world):
    # Reserve existing ordinary names first so generated replacements never steal them.
    used = {p.name.casefold() for p in world.people if not re.search(r'\d', p.name)}
    seen = set();changed = 0
    for person in world.people:
        if re.search(r'\d', person.name) or person.name.casefold() in seen:
            person.name = unique_name(world, person.id, used)
            used.add(person.name.casefold());changed += 1
        seen.add(person.name.casefold())
    return changed
