import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { login as loginRequest } from "../api/authApi";
import { apiRequest } from "../lib/apiClient";

const AuthContext = createContext(null);
const STORAGE_KEY = "school_management_auth";

function readStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => readStoredAuth());

  useEffect(() => {
    try {
      if (auth) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // localStorage may be unavailable (e.g. private browsing); session still works in-memory
    }
  }, [auth]);

  const value = useMemo(
    () => ({
      user: auth?.user ?? null,
      token: auth?.access_token ?? null,
      isAuthenticated: Boolean(auth?.access_token),
      async login(credentials) {
        const result = await loginRequest(credentials);
        setAuth(result);
        return result;
      },
      // Picks up changes made since login, e.g. the super admin switching a module on or off.
      async refreshUser() {
        if (!auth?.access_token) return;
        try {
          const { user } = await apiRequest("/auth/me", { token: auth.access_token });
          setAuth((prev) => (prev && prev.access_token === auth.access_token ? { ...prev, user: { ...prev.user, ...user } } : prev));
        } catch {
          // Offline or a stale token: keep what we have; API calls will report problems themselves.
        }
      },
      markPasswordChanged() {
        setAuth((prev) => (prev ? { ...prev, user: { ...prev.user, must_change_password: false } } : prev));
      },
      logout() {
        setAuth(null);
      },
    }),
    [auth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
