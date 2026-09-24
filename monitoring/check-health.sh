#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_directory=${REPOSTER_PROJECT_DIRECTORY:-/root/Code/reposter}
readonly state_directory=${MONITOR_STATE_DIRECTORY:-/var/lib/reposter-monitor}
readonly backup_success_file=${BACKUP_SUCCESS_FILE:-${state_directory}/last-backup-success}
readonly public_health_url=${MONITOR_HEALTH_URL:-https://www.uncle-vlad.ru/health}
readonly database_health_url=${MONITOR_DATABASE_HEALTH_URL:-https://www.uncle-vlad.ru/health/database}
readonly disk_warning_percent=${MONITOR_DISK_WARNING_PERCENT:-75}
readonly backup_max_age_hours=${MONITOR_BACKUP_MAX_AGE_HOURS:-26}

mkdir -p "$state_directory"

declare -a problems=()

disk_usage=$(df --output=pcent / | tail -n 1 | tr -dc '0-9')
if [[ -z "$disk_usage" ]]; then
  problems+=("Не удалось определить заполнение диска")
elif (( disk_usage >= disk_warning_percent )); then
  problems+=("Диск заполнен на ${disk_usage}% (порог ${disk_warning_percent}%)")
fi

cd "$project_directory"
running_services=$(docker compose -f compose.yaml -f compose.prod.yaml ps --status running --services)
for service in postgres app frontend; do
  if ! grep -qx "$service" <<<"$running_services"; then
    problems+=("Контейнер ${service} не запущен")
  fi
done

for unit in reposter-backup.service reposter-backup-verify.service; do
  if systemctl is-failed --quiet "$unit"; then
    problems+=("Системная задача завершилась ошибкой: ${unit}")
  fi
done

if ! curl --fail --silent --show-error --connect-timeout 5 --max-time 15 "$public_health_url" >/dev/null; then
  problems+=("Сайт не отвечает: ${public_health_url}")
fi

if ! curl --fail --silent --show-error --connect-timeout 5 --max-time 15 "$database_health_url" >/dev/null; then
  problems+=("Проверка базы не отвечает: ${database_health_url}")
fi

if [[ ! -f "$backup_success_file" ]]; then
  problems+=("Нет отметки об успешной резервной копии")
else
  current_epoch=$(date +%s)
  backup_epoch=$(stat -c %Y "$backup_success_file")
  backup_age_hours=$(( (current_epoch - backup_epoch) / 3600 ))
  if (( backup_age_hours > backup_max_age_hours )); then
    problems+=("Последняя успешная копия старше ${backup_age_hours} ч. (порог ${backup_max_age_hours} ч.)")
  fi
fi

if ((${#problems[@]})); then
  current_state=$(printf '%s\n' "${problems[@]}")
  previous_state=$(cat "${state_directory}/last-error" 2>/dev/null || true)
  if [[ "$current_state" != "$previous_state" ]]; then
    printf '%s\n' "$current_state" >"${state_directory}/last-error"
    "$project_directory/monitoring/notify-ntfy.sh" \
      "News Reposter: авария" \
      "$current_state" \
      urgent \
      rotating_light
  fi
  printf '%s\n' "$current_state" >&2
  exit 1
fi

if [[ -f "${state_directory}/last-error" ]]; then
  previous_state=$(cat "${state_directory}/last-error")
  rm -f "${state_directory}/last-error"
  printf -v recovery_message \
    'Все проверки снова проходят.\n\nПредыдущая проблема:\n%s' \
    "$previous_state"
  "$project_directory/monitoring/notify-ntfy.sh" \
    "News Reposter: восстановлено" \
    "$recovery_message" \
    default \
    white_check_mark
fi

printf 'All health checks passed\n'
