#!/bin/bash
set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }
check_dependencies() {
    log_step "Проверка зависимостей..."
    if ! command -v docker &>/dev/null; then log_error "Docker не установлен"; exit 1; fi
    if command -v docker-compose &>/dev/null; then COMPOSE="docker-compose"
    elif docker compose version &>/dev/null 2>&1; then COMPOSE="docker compose"
    else log_error "Docker Compose не установлен"; exit 1; fi
    log_info "Docker: $(docker --version)"
}
check_env() {
    log_step "Проверка .env..."
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warn ".env создан из .env.example — проверьте пароли"
        else log_error ".env не найден"; exit 1; fi
    fi
    log_info ".env найден"
}
deploy() {
    log_step "Сборка образов..."
    $COMPOSE build --no-cache
    log_step "Запуск контейнеров..."
    $COMPOSE up -d
    log_step "Статус:"
    $COMPOSE ps
}
main() {
    cd "$(dirname "$0")"
    check_dependencies
    check_env
    deploy
    log_info "✅ business-automation запущен на http://$(hostname -I | awk '{print $1}'):8080"
}
main "$@"
