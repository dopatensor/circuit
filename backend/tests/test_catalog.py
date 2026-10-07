import re

from app.seed.catalog import CAPABILITIES, CAPABILITY_IDS, TRAIT_IDS, TRAITS

SLUG = re.compile(r"^[a-z][a-z0-9_]*$")


def test_list_sizes_match_spec():
    assert 40 <= len(CAPABILITIES) <= 80
    assert 20 <= len(TRAITS) <= 30


def test_ids_are_unique_slugs():
    assert len(CAPABILITY_IDS) == len(CAPABILITIES)
    assert len(TRAIT_IDS) == len(TRAITS)
    assert all(SLUG.match(i) for i in CAPABILITY_IDS | TRAIT_IDS)


def test_every_entry_is_described():
    assert all(c.name and c.category and c.description for c in CAPABILITIES)
    assert all(t.name and t.description for t in TRAITS)
