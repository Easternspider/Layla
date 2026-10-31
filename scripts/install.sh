#!/usr/bin/env bash
# Одна команда: HTTP на этой машине или HTTPS на указанном домене.
#   bash scripts/install.sh
#   bash scripts/install.sh example.com
#   curl -fsSL https://raw.githubusercontent.com/Easternspider/Layla/main/scripts/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/Easternspider/Layla/main/scripts/install.sh | bash -s -- example.com
set -euo pipefail

REPO="${LAYLA_REPO:-https://github.com/Easternspider/Layla.git}"
DEST="${LAYLA_DIR:-$HOME/Layla}"

die() { printf 'Layla: %s\n' "$1" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "не найдено: $1"
}

rand_hex() { openssl rand -hex "$1"; }

fernet_key() {
  if command -v python3 >/dev/null 2>&1 && python3 -c 'from cryptography.fernet import Fernet' >/dev/null 2>&1; then
    python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
    return
  fi
  openssl rand 32 | openssl base64 -A | tr '+/' '-_'
}

set_env() {
  local key="$1" value="$2" file="$3"
  if grep -q "^${key}=" "$file"; then
    grep -v "^${key}=" "$file" > "${file}.tmp"
    printf '%s=%s\n' "$key" "$value" >> "${file}.tmp"
    mv "${file}.tmp" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

valid_domain() {
  [[ "$1" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$ ]]
}

enter_repo() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
  if [[ -n "$here" && -f "$here/../docker-compose.yml" ]]; then
    cd "$here/.."
    return
  fi
  if [[ -f docker-compose.yml && -f .env.example ]]; then
    return
  fi
  need git
  if [[ ! -f "$DEST/docker-compose.yml" ]]; then
    git clone --depth 1 "$REPO" "$DEST"
  fi
  cd "$DEST"
}

domain="${1:-}"
if [[ -z "$domain" && -r /dev/tty ]]; then
  read -r -p "Домен для HTTPS (Enter — только HTTP): " domain </dev/tty || true
fi
domain="${domain#"${domain%%[![:space:]]*}"}"
domain="${domain%"${domain##*[![:space:]]}"}"
domain="${domain#http://}"
domain="${domain#https://}"
domain="${domain%%/*}"

if [[ -n "$domain" ]]; then
  valid_domain "$domain" || die "нужен домен без схемы и порта, например example.com"
  case "$domain" in
    localhost|127.0.0.1) die "для localhost сертификат не выпустится. Запустите без домена." ;;
  esac
fi

need docker
need openssl
if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose=(docker-compose)
else
  die "нужен Docker Compose"
fi

enter_repo

if [[ ! -f .env ]]; then
  cp .env.example .env
  set_env LAYLA_SECRET_KEY "$(fernet_key)" .env
  set_env LAYLA_JWT_SECRET "$(rand_hex 32)" .env
  set_env POSTGRES_PASSWORD "$(rand_hex 24)" .env
  set_env LITELLM_MASTER_KEY "sk-$(rand_hex 24)" .env
  fresh=1
else
  fresh=0
fi

if [[ -n "$domain" ]]; then
  set_env LAYLA_ENV prod .env
  set_env LAYLA_PUBLIC_HOST "$domain" .env
  set_env LAYLA_SITE_ADDRESS "$domain" .env
  set_env LAYLA_PREVIEW_ADDRESS "${domain}:8090" .env
elif [[ "$fresh" == 1 ]]; then
  set_env LAYLA_ENV dev .env
  set_env LAYLA_PUBLIC_HOST localhost .env
  set_env LAYLA_SITE_ADDRESS :80 .env
  set_env LAYLA_PREVIEW_ADDRESS :8090 .env
fi

site="$(grep '^LAYLA_SITE_ADDRESS=' .env | cut -d= -f2-)"
case "$site" in
  http://*)
    url="$site"
    preview="http://localhost:8090"
    ;;
  :80|"")
    url="http://$(hostname -I 2>/dev/null | awk '{print $1}')"
    [[ "$url" == "http://" ]] && url="http://localhost"
    preview="${url}:8090"
    ;;
  *)
    url="https://${site%%:*}"
    preview="https://${site%%:*}:8090"
    ;;
esac

printf 'Собираю Layla. Первый раз займёт несколько минут.\n'
"${compose[@]}" up -d --build

cat <<EOF

Готово: ${url}
Превью приложений: ${preview}
Логин администратора: $(grep '^LAYLA_ADMIN_EMAIL=' .env | cut -d= -f2-)
Пароль один раз на странице входа. Если окно уже закрыто:
  ${compose[*]} logs layla-core | grep Bootstrap
Порты 80 и 443 должны быть открыты. Для HTTPS запись DNS домена смотрит на этот сервер.
EOF
