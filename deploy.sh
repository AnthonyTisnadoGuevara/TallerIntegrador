#!/bin/bash
set -Eeuo pipefail

PROJECT_DIR="/var/www/TallerIntegrador"
LOG_DIR="$PROJECT_DIR/logs/deployments"
TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
LOG_FILE="$LOG_DIR/deploy_$TIMESTAMP.log"

mkdir -p "$LOG_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log_info() {
  echo "[$(timestamp)] [INFO] $*"
}

log_success() {
  echo "[$(timestamp)] [SUCCESS] $*"
}

log_warning() {
  echo "[$(timestamp)] [WARNING] $*"
}

log_error() {
  echo "[$(timestamp)] [ERROR] $*"
}

on_error() {
  local line_number="$1"
  local failed_command="$2"
  local exit_code="$3"

  log_error "El despliegue falló"
  log_error "Comando fallido: $failed_command"
  log_error "Número de línea: $line_number"
  log_error "Código de salida: $exit_code"
  log_error "Archivo de log: $LOG_FILE"
}

trap 'on_error $LINENO "$BASH_COMMAND" $?' ERR

run_step() {
  local label="$1"
  shift

  log_info "Iniciando: $label"

  if "$@"; then
    log_success "Completado: $label"
  else
    local exit_code="$?"
    log_error "Falló: $label"
    log_error "Comando: $*"
    log_error "Código de salida: $exit_code"
    return "$exit_code"
  fi
}

verify_required_files() {
  local required_files=(
    "docker-compose.yml"
    "backend/Dockerfile"
    "frontend/Dockerfile"
    "frontend/nginx.conf"
    "backend/.env"
  )

  local missing=0
  local file

  for file in "${required_files[@]}"; do
    if [[ -f "$file" ]]; then
      log_success "Archivo requerido encontrado: $file"
    else
      log_error "Falta archivo requerido: $file"
      missing=1
    fi
  done

  if [[ "$missing" -ne 0 ]]; then
    log_error "Falta uno o más archivos requeridos. Abortando despliegue."
    return 1
  fi
}

validate_container_running() {
  local container_name="$1"

  if docker ps --filter "name=$container_name" --filter "status=running" --format '{{.Names}}' | grep -Fxq "$container_name"; then
    docker ps --filter "name=$container_name" --filter "status=running"
    return 0
  fi

  log_error "El contenedor no está corriendo: $container_name"
  docker ps -a --filter "name=$container_name"
  return 1
}

retry_curl() {
  local url="$1"
  local max_attempts=5
  local delay_seconds=5
  local attempt

  for attempt in $(seq 1 "$max_attempts"); do
    log_info "Intento de curl $attempt/$max_attempts: $url"

    if curl -fsSI --max-time 20 "$url"; then
      log_success "curl exitoso: $url"
      return 0
    fi

    if [[ "$attempt" -lt "$max_attempts" ]]; then
      log_warning "curl falló para $url. Reintentando en ${delay_seconds}s..."
      sleep "$delay_seconds"
    fi
  done

  log_error "curl falló después de $max_attempts intentos: $url"
  return 1
}

log_info "Iniciando despliegue"
log_info "Fecha: $(date)"
log_info "Usuario: $(whoami)"
log_info "Hostname: $(hostname)"
log_info "Ruta inicial: $(pwd)"
log_info "Archivo de log: $LOG_FILE"

run_step "Cambiar al directorio del proyecto" cd "$PROJECT_DIR"

run_step "Mostrar estado actual de git" git status --short

# --- NUEVO: guardamos el commit actual ANTES de actualizar ---
PREVIOUS_COMMIT="$(git rev-parse HEAD)"

run_step "Obtener últimos cambios" git fetch origin
run_step "Cambiar a rama develop" git checkout develop
run_step "Traer últimos cambios (pull)" git pull origin develop
run_step "Mostrar último commit" git log -1 --oneline
run_step "Verificar existencia de archivos requeridos" verify_required_files

# --- NUEVO: comparamos commit antes/despues del pull ---
CURRENT_COMMIT="$(git rev-parse HEAD)"

if [[ "$PREVIOUS_COMMIT" == "$CURRENT_COMMIT" ]]; then
  log_info "No se detectaron commits nuevos ($CURRENT_COMMIT). Se omite el build y el reinicio de contenedores."
  SKIP_BUILD=1
else
  log_info "Se detectaron commits nuevos: $PREVIOUS_COMMIT -> $CURRENT_COMMIT"
  SKIP_BUILD=0
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  # --- CAMBIO: se quito --no-cache. Docker reutiliza capas cacheadas
  #     (por ejemplo la instalacion de dependencias) si esos archivos
  #     no cambiaron, y solo reconstruye lo que realmente cambio. ---
  run_step "Construir imágenes Docker (con caché de capas)" docker compose build

  # --- CAMBIO: en vez de "down" + "up -d", usamos "up -d" directo.
  #     Compose recrea SOLO los contenedores cuya imagen o configuracion
  #     cambio, dejando los demas corriendo sin interrupcion. ---
  run_step "Recrear contenedores modificados" docker compose up -d --remove-orphans
else
  # Nos aseguramos de que los contenedores estén arriba aunque no hubo build
  run_step "Asegurar que los contenedores estén corriendo" docker compose up -d --remove-orphans
fi

log_info "Esperando 5 segundos para que los contenedores inicialicen"
sleep 5

run_step "Mostrar contenedores en ejecución" docker ps
run_step "Validar que el contenedor backend esté corriendo" validate_container_running "taller_backend"
run_step "Validar que el contenedor frontend esté corriendo" validate_container_running "taller_frontend"
run_step "Mostrar logs del backend" docker logs taller_backend --tail 80
run_step "Mostrar logs del frontend" docker logs taller_frontend --tail 50

run_step "Validar configuración de Nginx" nginx -t

# --- CAMBIO: reiniciamos Nginx solo cuando hubo cambios desplegados
#     desde Git (nuevo commit). No detecta cambios especificos en
#     nginx.conf, solo evita reinicios innecesarios cuando no se
#     desplego nada nuevo. ---
if [[ "$SKIP_BUILD" -eq 0 ]]; then
  run_step "Reiniciar Nginx" systemctl restart nginx
else
  log_info "Se omite el reinicio de Nginx (no se desplegaron cambios)"
fi

run_step "Probar backend localmente" retry_curl "http://127.0.0.1:8000/docs"
run_step "Probar frontend localmente" retry_curl "http://127.0.0.1:8080"
run_step "Probar frontend en producción" retry_curl "https://taller-mejoracontinua.duckdns.org"
run_step "Probar Swagger en producción" retry_curl "https://taller-mejoracontinua.duckdns.org/docs"

log_success "Despliegue completado exitosamente"
log_success "URL del frontend: https://taller-mejoracontinua.duckdns.org"
log_success "URL de Swagger: https://taller-mejoracontinua.duckdns.org/docs"
log_success "Archivo de log: $LOG_FILE"
