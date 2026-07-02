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

  log_error "Deployment failed"
  log_error "Failed command: $failed_command"
  log_error "Line number: $line_number"
  log_error "Exit code: $exit_code"
  log_error "Log file: $LOG_FILE"
}

trap 'on_error $LINENO "$BASH_COMMAND" $?' ERR

run_step() {
  local label="$1"
  shift

  log_info "Starting: $label"

  if "$@"; then
    log_success "Completed: $label"
  else
    local exit_code="$?"
    log_error "Failed: $label"
    log_error "Command: $*"
    log_error "Exit code: $exit_code"
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
      log_success "Required file found: $file"
    else
      log_error "Required file missing: $file"
      missing=1
    fi
  done

  if [[ "$missing" -ne 0 ]]; then
    log_error "One or more required files are missing. Aborting deployment."
    return 1
  fi
}

validate_container_running() {
  local container_name="$1"

  if docker ps --filter "name=$container_name" --filter "status=running" --format '{{.Names}}' | grep -Fxq "$container_name"; then
    docker ps --filter "name=$container_name" --filter "status=running"
    return 0
  fi

  log_error "Container is not running: $container_name"
  docker ps -a --filter "name=$container_name"
  return 1
}

retry_curl() {
  local url="$1"
  local max_attempts=5
  local delay_seconds=5
  local attempt

  for attempt in $(seq 1 "$max_attempts"); do
    log_info "curl attempt $attempt/$max_attempts: $url"

    if curl -fsSI --max-time 20 "$url"; then
      log_success "curl succeeded: $url"
      return 0
    fi

    if [[ "$attempt" -lt "$max_attempts" ]]; then
      log_warning "curl failed for $url. Retrying in ${delay_seconds}s..."
      sleep "$delay_seconds"
    fi
  done

  log_error "curl failed after $max_attempts attempts: $url"
  return 1
}

log_info "Starting deployment"
log_info "Date: $(date)"
log_info "User: $(whoami)"
log_info "Hostname: $(hostname)"
log_info "Initial path: $(pwd)"
log_info "Log file: $LOG_FILE"

run_step "Move to project directory" cd "$PROJECT_DIR"

run_step "Show current git status" git status --short
run_step "Fetch latest changes" git fetch origin
run_step "Checkout develop" git checkout develop
run_step "Pull latest changes" git pull origin develop
run_step "Show latest commit" git log -1 --oneline
run_step "Verify required files exist" verify_required_files

run_step "Stop existing containers" docker compose down
run_step "Build Docker images" docker compose build --no-cache
run_step "Start containers" docker compose up -d

log_info "Waiting 5 seconds for containers to initialize"
sleep 5

run_step "Show running containers" docker ps
run_step "Validate backend container is running" validate_container_running "taller_backend"
run_step "Validate frontend container is running" validate_container_running "taller_frontend"
run_step "Show backend logs" docker logs taller_backend --tail 80
run_step "Show frontend logs" docker logs taller_frontend --tail 50

run_step "Validate Nginx configuration" nginx -t
run_step "Restart Nginx" systemctl restart nginx

run_step "Test backend locally" retry_curl "http://127.0.0.1:8000/docs"
run_step "Test frontend locally" retry_curl "http://127.0.0.1:8080"
run_step "Test production frontend" retry_curl "https://taller-mejoracontinua.duckdns.org"
run_step "Test production Swagger" retry_curl "https://taller-mejoracontinua.duckdns.org/docs"

log_success "Deployment completed successfully"
log_success "Frontend URL: https://taller-mejoracontinua.duckdns.org"
log_success "Swagger URL: https://taller-mejoracontinua.duckdns.org/docs"
log_success "Log file: $LOG_FILE"
