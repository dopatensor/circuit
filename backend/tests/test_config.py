import pytest
from pydantic import ValidationError

from app.config import Settings


def test_demo_auth_refused_in_production():
    with pytest.raises(ValidationError, match="DEMO_AUTH"):
        Settings(_env_file=None, env="production", demo_auth=True)


def test_demo_auth_allowed_in_production_when_demo_public():
    s = Settings(_env_file=None, env="production", demo_auth=True, demo_public=True)
    assert s.demo_auth and s.demo_public


def test_demo_auth_allowed_in_development():
    assert Settings(_env_file=None, env="development", demo_auth=True).demo_auth


def test_cors_origins_parsed_from_comma_separated_string():
    s = Settings(_env_file=None, cors_origins="http://a.test, http://b.test")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]
