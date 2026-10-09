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
    proof,
    startup_map,
    startups,
)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def test_every_write_endpoint_records_an_event():
    missing = []
    for module in (admin, auth, intros, jobs, matches, members, needs, onboarding,
                   proof, startup_map, startups):  # fmt: skip
        for route in module.router.routes:
            if route.methods & WRITE_METHODS:
                source = inspect.getsource(route.endpoint)
                # Directly, through the intros module's shared _done() helper, or through
                # the GitHub service (connect and disconnect record their own events).
                helpers = ("record_event", "_done(", "service.connect(", "service.disconnect(")
                if not any(h in source for h in helpers):
                    missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, missing
