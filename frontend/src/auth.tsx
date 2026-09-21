import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  api,
  ApiError,
  AUTH_SESSION_EXPIRED_EVENT,
  CurrentUser,
  LoginCredentials,
  PasswordChange,
} from "./api";

export type AuthStatus = "loading" | "anonymous" | "authenticated" | "unavailable";

type AuthContextValue = {
  status: AuthStatus;
  user: CurrentUser | null;
  error: string;
  login: (credentials: LoginCredentials) => Promise<void>;
  changePassword: (passwords: PasswordChange) => Promise<void>;
  logout: (allSessions?: boolean) => Promise<void>;
  restore: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState("");

  const restore = useCallback(async () => {
    setStatus("loading");
    setError("");
    try {
      const currentUser = await api.currentUser();
      setUser(currentUser);
      setStatus("authenticated");
    } catch (exc) {
      setUser(null);
      if (exc instanceof ApiError && exc.status === 401) {
        setStatus("anonymous");
        return;
      }
      setError(exc instanceof Error ? exc.message : "Не удалось проверить сессию");
      setStatus("unavailable");
    }
  }, []);

  useEffect(() => {
    void restore();

    const handleExpiredSession = () => {
      setUser(null);
      setError("");
      setStatus("anonymous");
    };
    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleExpiredSession);
    return () => {
      window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleExpiredSession);
    };
  }, [restore]);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const currentUser = await api.login(credentials);
    setUser(currentUser);
    setError("");
    setStatus("authenticated");
  }, []);

  const changePassword = useCallback(async (passwords: PasswordChange) => {
    const currentUser = await api.changePassword(passwords);
    setUser(currentUser);
    setError("");
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async (allSessions = false) => {
    if (allSessions) {
      await api.logoutAll();
    } else {
      await api.logout();
    }
    setUser(null);
    setError("");
    setStatus("anonymous");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, error, login, changePassword, logout, restore }),
    [status, user, error, login, changePassword, logout, restore],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth должен использоваться внутри AuthProvider");
  }
  return value;
}
