#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_directory=${REPOSTER_PROJECT_DIRECTORY:-/root/Code/reposter}
readonly state_directory=${MONITOR_STATE_DIRECTORY:-/var/lib/reposter-monitor}
readonly backup_success_file=${BACKUP_SUCCESS_FILE:-${state_directory}/last-backup-success}

cd "$project_directory"

disk_usage=$(df --output=pcent / | tail -n 1 | tr -dc '0-9')
disk_available=$(df --output=avail -h / | tail -n 1 | xargs)

running_services=$(docker compose -f compose.yaml -f compose.prod.yaml \
  ps --status running --services)
healthy_services=0
for service in postgres app frontend; do
  if grep -qx "$service" <<<"$running_services"; then
    healthy_services=$((healthy_services + 1))
  fi
done

if [[ -f "$backup_success_file" ]]; then
  backup_epoch=$(stat -c %Y "$backup_success_file")
  current_epoch=$(date +%s)
  backup_age_hours=$(( (current_epoch - backup_epoch) / 3600 ))
  last_backup=$(date --date="@${backup_epoch}" '+%d.%m.%Y %H:%M %Z')
  backup_line="Последняя копия: ${last_backup} (${backup_age_hours} ч. назад)"
else
  backup_line="Последняя копия: отметка отсутствует"
fi

if systemctl is-failed --quiet reposter-backup-verify.service; then
  verification="ошибка"
else
  verification="без ошибок"
fi

printf -v message \
  '%s\nКонтейнеры: %s из 3 работают\nДиск: %s%% занято, свободно %s\nПроверка хранилища: %s' \
  "$backup_line" \
  "$healthy_services" \
  "$disk_usage" \
  "$disk_available" \
  "$verification"

"$project_directory/monitoring/notify-ntfy.sh" \
  "News Reposter: недельная сводка" \
  "$message" \
  default \
  bar_chart,floppy_disk

printf 'Weekly summary sent successfully\n'
