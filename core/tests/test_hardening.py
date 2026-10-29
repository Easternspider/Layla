"""Тесты прод-валидации конфигурации (спец. §7.5-§7.6)."""
from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import Settings


def test_dev_has_no_prod_problems():
    s = Settings(LAYLA_ENV="dev", LAYLA_PUBLIC_HOST="localhost", LAYLA_SITE_ADDRESS="http://localhost")
    assert s.validate_for_prod() == []


def test_prod_requires_secret_key():
    s = Settings(LAYLA_ENV="prod", LAYLA_SECRET_KEY="", LAYLA_JWT_SECRET="x" * 40)
    problems = s.validate_for_prod()
    assert any("LAYLA_SECRET_KEY" in p for p in problems)


def test_prod_rejects_default_jwt():
    s = Settings(LAYLA_ENV="prod", LAYLA_SECRET_KEY="k", LAYLA_JWT_SECRET="dev-insecure-jwt-secret")
    problems = s.validate_for_prod()
    assert any("JWT" in p for p in problems)


def test_prod_ok_with_real_secrets():
    s = Settings(
        LAYLA_ENV="prod",
        LAYLA_SECRET_KEY=Fernet.generate_key().decode(),
        LAYLA_JWT_SECRET="a" * 40,
        POSTGRES_PASSWORD="not-the-default-password",
        LITELLM_MASTER_KEY="sk-real-master-key-value",
    )
    assert s.validate_for_prod() == []


def test_prod_rejects_placeholders():
    s = Settings(
        LAYLA_ENV="prod",
        LAYLA_SECRET_KEY="CHANGE_ME_generate_a_fernet_key",
        LAYLA_JWT_SECRET="CHANGE_ME_random_hex_64",
        POSTGRES_PASSWORD="layla",
        LITELLM_MASTER_KEY="CHANGE_ME_litellm_master_key",
    )
    problems = s.validate_for_prod()
    assert any("LAYLA_SECRET_KEY" in p for p in problems)
    assert any("JWT" in p for p in problems)
    assert any("POSTGRES_PASSWORD" in p for p in problems)
    assert any("LITELLM_MASTER_KEY" in p for p in problems)


def test_public_site_requires_real_secrets_even_in_dev():
    s = Settings(
        LAYLA_ENV="dev",
        LAYLA_PUBLIC_HOST="localhost",
        LAYLA_SITE_ADDRESS="https://layla.example",
        LAYLA_SECRET_KEY="CHANGE_ME_generate_a_fernet_key",
        LAYLA_JWT_SECRET="dev-insecure-jwt-secret",
        POSTGRES_PASSWORD="layla",
        LITELLM_MASTER_KEY="",
    )
    assert s.validate_for_prod()
