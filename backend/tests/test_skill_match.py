"""The student "match to my skills" score: pure function tests."""

from app.skill_match import skill_match

BACKEND_ROLE = {
    "title": "Backend Intern",
    "capabilities": ["backend_development", "data_engineering"],
}
DESIGN_ROLE = {"title": "Designer", "capabilities": ["ui_ux_design"]}


def test_strong_skills_on_every_required_capability_is_100():
    m = skill_match({"backend_development": 3, "data_engineering": 3}, [BACKEND_ROLE], [])
    assert m.score == 100
    assert m.best_role.title == "Backend Intern" and m.missing == []


def test_skill_level_matters():
    strong = skill_match({"backend_development": 3, "data_engineering": 3}, [BACKEND_ROLE], [])
    basic = skill_match({"backend_development": 1, "data_engineering": 1}, [BACKEND_ROLE], [])
    assert strong.score > basic.score == 50


def test_partial_coverage_reports_whats_missing():
    m = skill_match({"backend_development": 3}, [BACKEND_ROLE], [])
    assert m.score == 50
    assert m.matched == ["backend_development"] and m.missing == ["data_engineering"]


def test_best_role_is_chosen():
    m = skill_match({"ui_ux_design": 2}, [BACKEND_ROLE, DESIGN_ROLE], [])
    assert m.best_role.title == "Designer" and m.score == 80


def test_needs_add_up_to_20_percent():
    skills = {"backend_development": 3, "data_engineering": 3}
    without = skill_match(skills, [BACKEND_ROLE], ["marketing"])
    with_need = skill_match(skills, [BACKEND_ROLE], ["data_engineering"])
    assert without.score == 80 and with_need.score == 100


def test_no_roles_scores_on_needs_only():
    m = skill_match({"marketing": 2}, [], ["marketing", "fundraising"])
    assert m.best_role is None and m.score == 40 and m.missing == ["fundraising"]


def test_no_skills_is_zero():
    assert skill_match({}, [BACKEND_ROLE], ["marketing"]).score == 0


def test_college_is_not_an_input():
    # The signature itself is the guarantee: there is no way to pass a college.
    import inspect

    assert list(inspect.signature(skill_match).parameters) == [
        "skills", "open_roles", "need_capabilities",
    ]  # fmt: skip
