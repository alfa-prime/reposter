import { AlertTriangle, Check, ExternalLink, RefreshCw, RotateCcw, Search } from "lucide-react";
import { QueueItem } from "../api";

type Props = {
  item: QueueItem;
  busy: boolean;
  onCheck: () => void;
  onMarkPublished: () => void;
  onRetry: () => void;
  onReturnToWork: () => void;
};

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value));
}

const attemptLabels: Record<string, string> = {
  sending: "Отправляется",
  confirmed: "Подтверждена",
  failed: "Ошибка",
  unknown: "Результат неизвестен",
};

export function PublicationRecoveryPanel({ item, busy, onCheck, onMarkPublished, onRetry, onReturnToWork }: Props) {
  const attempts = item.publication?.attempt_history ?? [];
  const latest = attempts[0];
  const checked = (latest?.check_count ?? 0) > 0;

  return (
    <section className="publication-recovery">
      <div className="publication-recovery-title">
        <AlertTriangle size={22}/>
        <div>
          <strong>Не удалось подтвердить результат публикации</strong>
          <p>MAX мог принять пост, но приложение не получило надёжный ответ. Не повторяйте отправку, пока не проверите канал — иначе появится дубликат.</p>
        </div>
      </div>

      <div className="publication-recovery-actions">
        <button className="primary" onClick={onCheck} disabled={busy}><Search size={17}/>Проверить в MAX</button>
        {item.target_url && <a className="secondary button-link" href={item.target_url} target="_blank" rel="noreferrer"><ExternalLink size={17}/>Открыть канал</a>}
        <button className="secondary" onClick={onMarkPublished} disabled={busy}><Check size={17}/>Отметить опубликованным</button>
        <button className="danger" onClick={onRetry} disabled={busy || !checked} title={!checked ? "Сначала выполните проверку MAX" : "Повтор может создать дубликат"}><RefreshCw size={17}/>Повторить</button>
        <button className="secondary" onClick={onReturnToWork} disabled={busy || !checked}><RotateCcw size={17}/>Вернуть в работу</button>
      </div>

      <details className="publication-attempts">
        <summary>История попыток ({attempts.length})</summary>
        {attempts.map((attempt) => (
          <div className="publication-attempt" key={attempt.publication_attempt_id}>
            <span>Попытка №{attempt.attempt_number}</span>
            <strong>{attemptLabels[attempt.status] ?? attempt.status}</strong>
            <time>{formatDate(attempt.started_at)}</time>
            {attempt.check_count > 0 && <small>Проверок MAX: {attempt.check_count}</small>}
            {attempt.error_message && <small>{attempt.error_message}</small>}
          </div>
        ))}
      </details>
    </section>
  );
}
