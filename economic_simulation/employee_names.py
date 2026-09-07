"""Deterministic human names, independent of economic random streams."""
import hashlib
import re

FIRST = tuple('Alex Avery Bailey Cameron Casey Charlie Dakota Drew Elliot Emerson Finley Hayden Jamie Jordan Jules Kai Kendall Lane Logan Marley Morgan Parker Peyton Quinn Reese Riley Robin Rowan Sage Sam Sidney Skyler Taylor Adrian Amelia Aria Arthur Audrey Benjamin Blake Caleb Clara Daniel Elena Eli Elise Ethan Eva Felix Gabriel Grace Hannah Harper Hazel Henry Isaac Isla Ivy Jasper Jonah Joseph Julian Leah Leo Liam Lily Lucas Lucy Maya Miles Naomi Nathan Noah Nora Oliver Owen Paige Penelope Rachel Ruby Sadie Samuel Sarah Sebastian Sophia Stella Theo Thomas Violet Vivian Wesley William Zoe'.split())
LAST = tuple('Adams Allen Anderson Archer Bailey Baker Bennett Blake Brooks Brown Campbell Carter Chen Clarke Cole Collins Cooper Davis Dawson Diaz Ellis Evans Fisher Flores Ford Foster Fox Garcia Gray Green Griffin Hall Hamilton Harris Hayes Hill Howard Hughes Jackson James Jensen Johnson Jones Kelly Kim King Lane Lawson Lee Lewis Martin Mason Miller Mitchell Moore Morgan Morris Murphy Nelson Nguyen Ortiz Palmer Park Parker Patel Perry Peterson Phillips Porter Powell Price Reed Reyes Reynolds Rivera Roberts Robinson Ross Russell Sanders Scott Shaw Simmons Singh Smith Spencer Stone Sullivan Taylor Thomas Thompson Torres Turner Walker Ward Watson Wells West White Williams Wilson Wood Wright Young'.split())

# Broader contemporary names, including Vermont's French-Canadian heritage.
# Names do not determine qualifications, personality or employment outcomes.
FIRST += tuple("Abigail Ada Adelaide Adele Aiden Aisha Alana Albert Alessandra Alice Alison Alma Amara Amir Ana Anika Anne Anthony Anton Arjun Asher Astrid Beatrice Bella Bennett Bethany Bianca Bridget Brianna Callum Caroline Cassia Catherine Cecile Celeste Chloe Christian Claire Colin Cora Corinne Cyrus Daisy Dalia Darius Dean Delilah Diana Dominic Dorothy Dylan Edith Edward Eleanor Elias Eliza Eloise Emile Emilia Eric Esther Esme Evelyn Ezra Fiona Frances Freya Genevieve George Georgia Gideon Gloria Graham Greta Guinevere Hugo Imogen Ingrid Iris Isabel Jacqueline Jane Jean Jeremy Joanna Joel Josephine Joshua Josie Judith Kieran Kira Lara Laurel Layla Leon Leona Lillian Linnea Louise Lydia Madeleine Maeve Malcolm Marcus Margot Marianne Marie Matilda Mateo Max Micah Miriam Nadia Nancy Natalie Neil Nikhil Nina Noelle Nolan Odette Omar Opal Oscar Otto Pablo Paloma Patricia Peter Phoebe Priya Rafael Ramona Remy Renee Rhys Rosa Rosalind Rose Ruth Sabrina Salma Sasha Selena Simone Simon Soren Sylvie Talia Teresa Thalia Tobias Tristan Uma Valerie Vera Victor Viola Walter Warren Willa Xavier Yara Yasmin Yusuf Zain Zora".split())
LAST += tuple("Abbott Abbott Ames Ashby Atwood Audet Avery Barlow Barrett Beaulieu Beaumont Beck Bell Bergeron Bisset Bishop Bouchard Boudreau Bowen Boyle Bradford Brady Brennan Briggs Britton Burton Caldwell Callahan Cameron Caron Chandler Chapman Charest Choi Christensen Cormier Costa Cote Couture Crane Cross Crowley Curtis Dallaire Dalton Daniels Das Desai Deschamps Desjardins Donovan Doyle Dubois Dufour Dumas Dumont Dupont Durham Eaton Edwards Farrell Faulkner Fernandez Fletcher Fontaine Fournier Fraser Freeman Gallagher Gagnon Gauthier Gibson Gilbert Glover Grant Graves Hale Harding Hart Hartley Harvey Hathaway Hawkins Hebert Henderson Henry Hickey Holloway Holmes Hopkins Horton Houston Hutchins Ibrahim Ingram Jacobs Jacques Jarvis Jennings Joshi Kaplan Kaur Keane Keating Keller Kennedy Kirby Knox Lambert Lang Langlois Lapointe Larsen Laurent LeBlanc Leclerc Lefebvre Leonard Levesque Li Lin Little Livingston Lowell MacDonald MacLeod Mahoney Marchand Marsh Martel Matthews McCarthy McConnell McKenna Medina Mercier Meyer Michaud Middleton Monroe Montgomery Moreau Nadeau Nash Neal Noel Nolan Novak Oakes OBrien OConnor Oliver Page Pelletier Perkins Pierce Poirier Pratt Quinn Raymond Reeves Riley Robichaud Roy Russo Savard Sawyer Schneider Shah Sinclair Sloan Snow Sosa StPierre Steele Sullivan Sutton Swanson Tanner Thibault Todd Tremblay Tucker Underwood Valdez Vasquez Vincent Wagner Walsh Warner Weaver Webster Whitney Wilcox Winters Wolfe Wong Wu Zimmer".split())
FIRST = tuple(dict.fromkeys(FIRST))
LAST = tuple(dict.fromkeys(LAST))


def unique_name(world, identity, used=None):
    used = {p.name.casefold() for p in world.people} if used is None else used
    from collections import Counter
    from math import gcd
    used = {name.casefold() for name in used}
    first_counts=Counter(name.split()[0] for name in used if name.split())
    last_counts=Counter(name.split()[-1] for name in used if name.split())
    digest=hashlib.sha256(f'{world.seed}:{identity}:person-name-v2'.encode()).digest()
    start=int.from_bytes(digest[:8],'big');size=len(FIRST)*len(LAST)
    stride=int.from_bytes(digest[8:16],'big') % size or 1
    while gcd(stride,size)!=1:stride+=1
    best=None
    for index in range(size):
        value=(start+index*stride) % size
        first,last=FIRST[value//len(LAST)],LAST[value % len(LAST)]
        name=first+' '+last
        if name.casefold() in used:continue
        score=first_counts[first.casefold()]+last_counts[last.casefold()]
        if best is None or score<best[0]:best=(score,name)
        if score==0 or (index>=63 and best):return best[1]
    if best:return best[1]
    # Large worlds can use genuine middle names rather than numeric suffixes.
    for middle in FIRST:
        for index in range(size):
            value=(start+index*stride) % size
            name=FIRST[value//len(LAST)]+' '+middle+' '+LAST[value % len(LAST)]
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
