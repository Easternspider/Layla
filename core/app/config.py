"""Application settings, loaded from environment (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote, urlparse

from cryptography.fernet import Fernet
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _host_of(value: str) -> str:
    text = (value or "").strip()
    if not text or text in {":80", ":443"}:
        return ""
    if "://" not in text:
        text = "https://" + text
    return (urlparse(text).hostname or "").lower().rstrip(".")


def _local_host(host: str) -> bool:
    return host in {"", "localhost", "127.0.0.1", "::1"}


def _placeholder(value: str) -> bool:
    raw = (value or "").strip().lower()
    return (not raw) or "change_me" in raw or raw in {
        "dev-insecure-jwt-secret", "layla-dev-only-insecure-key",
    }


def _is_fernet(value: str) -> bool:
    try:
        Fernet((value or "").encode())
    except (ValueError, TypeError):
        return False
    return True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # --- General ---
    env: str = Field(default="dev", alias="LAYLA_ENV")
    public_host: str = Field(default="localhost", alias="LAYLA_PUBLIC_HOST")
    # Адрес, который слушает Caddy. Пусто или localhost — стенд не считается публичным.
    site_address: str = Field(default="", alias="LAYLA_SITE_ADDRESS")
    # E-mail админа, создаваемого при первой установке (если пользователей ещё нет).
    # Домен .app — валидный (в отличие от .local), почта туда не шлётся: это лишь
    # логин. Замените на свой реальный e-mail через LAYLA_ADMIN_EMAIL.
    admin_email: str = Field(default="admin@layla.app", alias="LAYLA_ADMIN_EMAIL")
    # Открытая саморегистрация. По умолчанию ВЫКЛ: пользователей заводит админ.
    # Включите, если хотите разрешить всем регистрироваться самостоятельно.
    allow_open_registration: bool = Field(
        default=False, alias="LAYLA_ALLOW_OPEN_REGISTRATION"
    )

    # --- Crypto / auth ---
    # Fernet key for secrets-at-rest. A dev fallback is generated if unset so
    # the app boots locally; in prod LAYLA_SECRET_KEY MUST be provided.
    secret_key: str = Field(default="", alias="LAYLA_SECRET_KEY")
    jwt_secret: str = Field(default="dev-insecure-jwt-secret", alias="LAYLA_JWT_SECRET")
    jwt_ttl_minutes: int = Field(default=1440, alias="LAYLA_JWT_TTL_MINUTES")

    # --- Database ---
    # DATABASE_URL можно задать явно (напр. внешняя БД). Если он пуст — собирается
    # из POSTGRES_* ниже, чтобы смена пароля не рассинхронизировалась с URL.
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_user: str = Field(default="layla", alias="POSTGRES_USER")
    postgres_password: str = Field(default="layla", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="layla", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    @model_validator(mode="after")
    def _assemble_database_url(self) -> Settings:
        """Собрать DATABASE_URL из частей, если он не задан явно.

        Логин/пароль URL-кодируются — иначе символы @ / : в пароле ломают строку
        подключения. Явный DATABASE_URL (в т.ч. sqlite в тестах) имеет приоритет.
        """
        if not self.database_url:
            user = quote(self.postgres_user, safe="")
            password = quote(self.postgres_password, safe="")
            self.database_url = (
                f"postgresql+asyncpg://{user}:{password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Куда клонируются репозитории / создаются проекты (Settings -> General).
    projects_dir: str = Field(default="./data/projects", alias="LAYLA_PROJECTS_DIR")
    pentest_company: str = Field(default='', alias='LAYLA_PENTEST_COMPANY')
    pentest_responsible_name: str = Field(default='', alias='LAYLA_PENTEST_RESPONSIBLE_NAME')
    pentest_employee_identifier: str = Field(default='', alias='LAYLA_PENTEST_EMPLOYEE_IDENTIFIER')

    # Адреса анонимизирующих маршрутов для egress-проб (спец. §7.4).
    tor_addr: str = Field(default="127.0.0.1:9050", alias="LAYLA_TOR_ADDR")
    proxy_addr: str = Field(default="", alias="LAYLA_PROXY_ADDR")

    # --- Запуск кода ---
    # Песочница проекта (свой сервис sandbox/): команды с зависимостями в рабочей копии.
    # unix:///путь/к/сокету или http://хост:порт. Пусто — запуск команд недоступен.
    sandbox_url: str = Field(default="unix:///run/layla-sandbox/sandbox.sock", alias="LAYLA_SANDBOX_URL")
    # Piston: компиляция и запуск программ на десятках языков без зависимостей.
    piston_url: str = Field(default="http://piston:2000", alias="LAYLA_PISTON_URL")
    # Превью приложений открывается на отдельном адресе (другой порт Caddy): так код превью
    # не работает от имени Лейлы. LAYLA_PREVIEW_URL — полный адрес, если он отличается от
    # «та же схема и хост, порт LAYLA_PREVIEW_PORT».
    preview_port: int = Field(default=8090, alias="LAYLA_PREVIEW_PORT")
    preview_url: str = Field(default="", alias="LAYLA_PREVIEW_URL")

    # --- LiteLLM ---
    litellm_base_url: str = Field(default="http://localhost:4000", alias="LITELLM_BASE_URL")
    litellm_master_key: str = Field(default="", alias="LITELLM_MASTER_KEY")

    @property
    def is_prod(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    def _reachable(self) -> bool:
        """Прод или адрес, который уже не локальный стенд."""
        if self.is_prod:
            return True
        return any(not _local_host(host) for host in (_host_of(self.public_host), _host_of(self.site_address)))

    def validate_for_prod(self) -> list[str]:
        """Секреты-примеры не должны обслуживать доступный снаружи стенд."""
        if not self._reachable():
            return []
        problems: list[str] = []
        if not _is_fernet(self.secret_key) or _placeholder(self.secret_key):
            problems.append(
                "LAYLA_SECRET_KEY должен быть настоящим ключом Fernet, не примером CHANGE_ME"
            )
        if _placeholder(self.jwt_secret) or len((self.jwt_secret or "").strip()) < 32:
            problems.append("LAYLA_JWT_SECRET должен быть своим секретом не короче 32 символов, не примером")
        if _placeholder(self.postgres_password) or (self.postgres_password or "").strip().lower() == "layla":
            problems.append("POSTGRES_PASSWORD нельзя оставлять примером или значением layla")
        if _placeholder(self.litellm_master_key):
            problems.append("LITELLM_MASTER_KEY нельзя оставлять пустым или примером CHANGE_ME")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
