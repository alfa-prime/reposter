import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Ban,
  CheckCircle2,
  Clipboard,
  KeyRound,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  UserRoundCheck,
  X,
} from "lucide-react";
import { AdminRole, AdminUser, api } from "../api";
import { useAuth } from "../auth";
import { generateTemporaryPassword, toggleRoleCode } from "../userAdmin";
import "../users.css";

type CreateForm = {
  username: string;
  displayName: string;
  temporaryPassword: string;
  roleCodes: string[];
};

const emptyCreateForm = (): CreateForm => ({
  username: "",
  displayName: "",
  temporaryPassword: generateTemporaryPassword(),
  roleCodes: [],
});

function formatDate(value?: string | null): string {
  if (!value) return "Ещё не входил";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function RolePicker({
  roles,
  selected,
  disabled,
  onChange,
}: {
  roles: AdminRole[];
  selected: string[];
  disabled: boolean;
  onChange: (codes: string[]) => void;
}) {
  return (
    <div className="user-role-picker">
      {roles.map((role) => (
        <label key={role.code} className={selected.includes(role.code) ? "selected" : ""}>
          <input
            type="checkbox"
            checked={selected.includes(role.code)}
            disabled={disabled}
            onChange={() => onChange(toggleRoleCode(selected, role.code))}
          />
          <span>
            <strong>{role.name}</strong>
            <small>{role.description || `${role.permissions.length} разрешений`}</small>
          </span>
        </label>
      ))}
    </div>
  );
}

type CapabilityColumn = {
  label: string;
  read: string[];
  manage: string[];
  readLabel: string;
  manageLabel: string;
};

const capabilityColumns: CapabilityColumn[] = [
  {
    label: "Очередь",
    read: ["queue.read"],
    manage: ["queue.edit", "queue.rewrite", "queue.submit"],
    readLabel: "Просмотр",
    manageLabel: "Подготовка",
  },
  {
    label: "Публикация",
    read: ["queue.moderate", "queue.schedule"],
    manage: ["queue.publish"],
    readLabel: "Модерация",
    manageLabel: "Полный цикл",
  },
  {
    label: "Каналы и источники",
    read: ["sources.read", "targets.read", "scheduler.read"],
    manage: ["sources.manage", "targets.manage", "scheduler.manage"],
    readLabel: "Просмотр",
    manageLabel: "Управление",
  },
  {
    label: "Пользователи",
    read: ["users.read", "roles.read"],
    manage: ["users.manage", "roles.manage"],
    readLabel: "Просмотр",
    manageLabel: "Управление",
  },
];

function capabilityLabel(role: AdminRole, column: CapabilityColumn): string {
  if (column.manage.some((permission) => role.permissions.includes(permission))) {
    return column.manageLabel;
  }
  if (column.read.some((permission) => role.permissions.includes(permission))) {
    return column.readLabel;
  }
  return "Нет доступа";
}

function RoleComparison({ roles }: { roles: AdminRole[] }) {
  return (
    <div className="role-comparison">
      <div className="role-comparison-title">
        <strong>Сравнение ролей</strong>
        <span>Кратко о том, какие разделы и действия доступны каждой роли.</span>
      </div>
      <div className="role-comparison-scroll">
        <table>
          <thead>
            <tr>
              <th>Роль</th>
              {capabilityColumns.map((column) => <th key={column.label}>{column.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <tr key={role.code}>
                <th scope="row">{role.name}</th>
                {capabilityColumns.map((column) => {
                  const label = capabilityLabel(role, column);
                  return <td key={column.label} className={label === "Нет доступа" ? "muted" : ""}>{label}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>«Администратор» имеет полный доступ. «Выпускающий редактор» модерирует и публикует, «Редактор» готовит материалы, а «Наблюдатель» работает только в режиме просмотра.</p>
    </div>
  );
}

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const canManage = currentUser?.permissions.includes("users.manage") ?? false;
  const canReadRoles = currentUser?.permissions.includes("roles.read") ?? false;
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [roleCodes, setRoleCodes] = useState<string[]>([]);
  const [resetPassword, setResetPassword] = useState(generateTemporaryPassword);
  const [createForm, setCreateForm] = useState<CreateForm>(emptyCreateForm);
  const [createOpen, setCreateOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selected = useMemo(
    () => users.find((item) => item.user_id === selectedId) ?? null,
    [users, selectedId],
  );
  const isSelf = selected?.user_id === currentUser?.user_id;

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [userData, roleData] = await Promise.all([
        api.adminUsers(),
        canReadRoles ? api.adminRoles() : Promise.resolve([]),
      ]);
      setUsers(userData);
      setRoles(roleData);
      setSelectedId((current) => (
        current !== null && userData.some((item) => item.user_id === current)
          ? current
          : (userData[0]?.user_id ?? null)
      ));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить пользователей");
    } finally {
      setBusy(false);
    }
  }, [canReadRoles]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!selected) return;
    setDisplayName(selected.display_name);
    setRoleCodes(selected.roles.map((role) => role.code));
    setResetPassword(generateTemporaryPassword());
  }, [selected]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function replaceUser(updated: AdminUser) {
    setUsers((items) => items.map((item) => (
      item.user_id === updated.user_id ? updated : item
    )));
  }

  async function saveUser() {
    if (!selected) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await api.updateAdminUser(selected.user_id, {
        display_name: displayName,
        ...(!isSelf && canReadRoles ? { role_codes: roleCodes } : {}),
      });
      replaceUser(data);
      setNotice("Изменения пользователя сохранены.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось сохранить пользователя");
    } finally { setBusy(false); }
  }

  async function toggleActive() {
    if (!selected || isSelf) return;
    if (selected.is_active && !window.confirm(`Заблокировать пользователя «${selected.display_name}» и завершить его сессии?`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await api.updateAdminUser(selected.user_id, { is_active: !selected.is_active });
      replaceUser(data);
      setNotice(data.is_active ? "Пользователь разблокирован." : "Пользователь заблокирован, активные сессии завершены.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось изменить доступ");
    } finally { setBusy(false); }
  }

  async function revokeSessions() {
    if (!selected || isSelf) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.revokeAdminUserSessions(selected.user_id);
      setNotice(`Завершено активных сессий: ${result.revoked_sessions}.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось завершить сессии");
    } finally { setBusy(false); }
  }

  async function applyTemporaryPassword() {
    if (!selected || isSelf) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await api.resetAdminUserPassword(selected.user_id, resetPassword);
      replaceUser(data);
      setNotice("Временный пароль установлен, активные сессии завершены.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось сбросить пароль");
    } finally { setBusy(false); }
  }

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await api.createAdminUser({
        username: createForm.username,
        display_name: createForm.displayName,
        temporary_password: createForm.temporaryPassword,
        role_codes: createForm.roleCodes,
      });
      setUsers((items) => [...items, created].sort((a, b) => a.display_name.localeCompare(b.display_name, "ru")));
      setSelectedId(created.user_id);
      setCreateOpen(false);
      setCreateForm(emptyCreateForm());
      setNotice("Пользователь создан. Передайте ему временный пароль безопасным способом.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось создать пользователя");
    } finally { setBusy(false); }
  }

  async function copyPassword(value: string) {
    await navigator.clipboard.writeText(value);
    setNotice("Временный пароль скопирован.");
  }

  return (
    <section className="settings-page users-page">
      <header className="settings-page-head users-head">
        <div><p className="eyebrow">АДМИНИСТРИРОВАНИЕ · ДОСТУП</p><h1>Пользователи</h1></div>
        <div className="users-head-actions">
          <button className="secondary" onClick={() => void load()} disabled={busy}><RefreshCw size={16} />Обновить</button>
          {canManage && canReadRoles && <button className="primary" onClick={() => setCreateOpen(true)} disabled={busy}><Plus size={16} />Добавить пользователя</button>}
        </div>
      </header>

      {(error || notice) && <div className={error ? "toast error" : "toast"}>{error || notice}<button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

      <div className="users-layout">
        <div className="users-list-card">
          <div className="users-list-title"><span>Команда</span><strong>{users.length}</strong></div>
          <div className="users-list">
            {users.map((item) => (
              <button key={item.user_id} className={item.user_id === selectedId ? "active" : ""} onClick={() => setSelectedId(item.user_id)}>
                <span className="user-avatar">{item.display_name.trim().slice(0, 1).toUpperCase()}</span>
                <span className="user-list-copy"><strong>{item.display_name}</strong><small>@{item.username}</small></span>
                <span className={`user-dot ${item.is_active ? "active" : "blocked"}`} title={item.is_active ? "Активен" : "Заблокирован"} />
              </button>
            ))}
            {!busy && users.length === 0 && <p className="users-empty">Пользователи не найдены.</p>}
          </div>
        </div>

        <div className="user-detail-card">
          {!selected ? <div className="users-empty large">Выберите пользователя</div> : <>
            <div className="user-detail-head">
              <div><span className="user-avatar large">{selected.display_name.trim().slice(0, 1).toUpperCase()}</span><div><h2>{selected.display_name}</h2><p>@{selected.username}</p></div></div>
              <div className="user-badges">
                <span className={selected.is_active ? "positive" : "negative"}>{selected.is_active ? <CheckCircle2 size={14} /> : <Ban size={14} />}{selected.is_active ? "Активен" : "Заблокирован"}</span>
                {selected.must_change_password && <span className="warning"><KeyRound size={14} />Ожидает смены пароля</span>}
              </div>
            </div>

            <div className="user-section">
              <div className="user-section-title"><div><strong>Профиль и роли</strong><span>Последний вход: {formatDate(selected.last_login_at)}</span></div><ShieldCheck size={19} /></div>
              <label className="user-field"><span>Отображаемое имя</span><input value={displayName} disabled={!canManage || busy} onChange={(event) => setDisplayName(event.target.value)} /></label>
              {canReadRoles ? <RolePicker roles={roles} selected={roleCodes} disabled={!canManage || busy || Boolean(isSelf)} onChange={setRoleCodes} /> : <p className="user-hint">Для просмотра ролей требуется разрешение roles.read.</p>}
              {isSelf && <p className="user-hint">Свои роли и состояние нельзя изменить из этой карточки — так администратор не потеряет доступ случайно.</p>}
              {canManage && <div className="user-actions"><button className="primary" disabled={busy || !displayName.trim() || roleCodes.length === 0} onClick={() => void saveUser()}><Save size={16} />Сохранить</button><button className={selected.is_active ? "danger subtle" : "secondary"} disabled={busy || Boolean(isSelf)} onClick={() => void toggleActive()}>{selected.is_active ? <Ban size={16} /> : <UserRoundCheck size={16} />}{selected.is_active ? "Заблокировать" : "Разблокировать"}</button></div>}
            </div>

            {canManage && <div className="user-section security-section">
              <div className="user-section-title"><div><strong>Безопасность</strong><span>Сброс пароля сразу завершает все сессии</span></div><KeyRound size={19} /></div>
              <div className="temporary-password-row"><input type="text" value={resetPassword} disabled={busy || Boolean(isSelf)} onChange={(event) => setResetPassword(event.target.value)} /><button className="icon-button" title="Скопировать" disabled={Boolean(isSelf)} onClick={() => void copyPassword(resetPassword)}><Clipboard size={17} /></button><button className="secondary" disabled={busy || Boolean(isSelf)} onClick={() => setResetPassword(generateTemporaryPassword())}><RefreshCw size={15} />Новый</button></div>
              <div className="user-actions"><button className="secondary" disabled={busy || Boolean(isSelf) || resetPassword.length < 15} onClick={() => void applyTemporaryPassword()}><KeyRound size={16} />Установить временный пароль</button><button className="secondary" disabled={busy || Boolean(isSelf)} onClick={() => void revokeSessions()}><X size={16} />Завершить все сессии</button></div>
            </div>}
          </>}
        </div>
      </div>

      {createOpen && <div className="modal-backdrop" onMouseDown={() => setCreateOpen(false)}>
        <div className="modal-card user-create-modal" onMouseDown={(event) => event.stopPropagation()}>
          <div className="modal-head"><div><p className="eyebrow">НОВАЯ УЧЁТНАЯ ЗАПИСЬ</p><h2>Добавить пользователя</h2></div><button className="icon-button" onClick={() => setCreateOpen(false)}><X size={18} /></button></div>
          <form className="form-grid" onSubmit={(event) => void createUser(event)}>
            <label>Логин<input autoFocus value={createForm.username} onChange={(event) => setCreateForm({ ...createForm, username: event.target.value })} placeholder="ivan.petrov" required /></label>
            <label>Отображаемое имя<input value={createForm.displayName} onChange={(event) => setCreateForm({ ...createForm, displayName: event.target.value })} placeholder="Иван Петров" required /></label>
            <label className="wide">Временный пароль<span className="temporary-password-row"><input type="text" value={createForm.temporaryPassword} onChange={(event) => setCreateForm({ ...createForm, temporaryPassword: event.target.value })} minLength={15} required /><button type="button" className="icon-button" title="Скопировать" onClick={() => void copyPassword(createForm.temporaryPassword)}><Clipboard size={17} /></button><button type="button" className="secondary" onClick={() => setCreateForm({ ...createForm, temporaryPassword: generateTemporaryPassword() })}><RefreshCw size={15} />Новый</button></span><small>Не менее 15 символов. Пользователь сменит его после первого входа.</small></label>
            <div className="wide"><span className="form-label">Роли</span><RolePicker roles={roles} selected={createForm.roleCodes} disabled={busy} onChange={(codes) => setCreateForm({ ...createForm, roleCodes: codes })} /></div>
            <div className="wide"><RoleComparison roles={roles} /></div>
            <button className="primary" disabled={busy || createForm.roleCodes.length === 0}><Plus size={16} />Создать пользователя</button>
          </form>
        </div>
      </div>}
    </section>
  );
}
