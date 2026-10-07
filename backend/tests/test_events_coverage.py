"""F10: every product action writes an event. Guards against new endpoints that forget."""

import inspect

from app.api import (
    admin,
    auth,
    intros,
    jobs,
    matches,
    members,
    needs,
    onboarding,
    startup_map,
    startups,
)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def test_every_write_endpoint_records_an_event():
    missing = []
    for module in (admin, auth, intros, jobs, matches, members, needs, onboarding,
                   startup_map, startups):  # fmt: skip
        for route in module.router.routes:
            if route.methods & WRITE_METHODS:
                source = inspect.getsource(route.endpoint)
                # Directly, or through the intros module's shared _done() helper.
                if "record_event" not in source and "_done(" not in source:
                    missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, missing
