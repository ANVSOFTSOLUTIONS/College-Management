import * as SecureStore from "expo-secure-store";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "./api";

const KEY = "college_session";
const AuthContext = createContext(null);

// The signed-in user and token, kept in the phone's secure storage so the app opens signed in.
export function AuthProvider({ children }) {
  const [session, setSession] = useState(null); // { token, user }
  const [ready, setReady] = useState(false);

  useEffect(() => {
    SecureStore.getItemAsync(KEY)
      .then((raw) => raw && setSession(JSON.parse(raw)))
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  const save = useCallback(async (next) => {
    setSession(next);
    if (next) await SecureStore.setItemAsync(KEY, JSON.stringify(next));
    else await SecureStore.deleteItemAsync(KEY);
  }, []);

  const value = useMemo(
    () => ({
      ready,
      token: session?.token ?? null,
      user: session?.user ?? null,
      async login(credentials) {
        const result = await api("/auth/login", { method: "POST", body: { ...credentials, portal: "school" } });
        if (!["student", "parent", "teacher"].includes(result.user.role)) {
          throw new ApiError(403, "wrong_app", "This app is for students, parents and faculty. Admins use the website.");
        }
        await save({ token: result.access_token, user: result.user });
      },
      async refresh() {
        if (!session) return;
        try {
          const me = await api("/auth/me", { token: session.token });
          await save({ ...session, user: me.user });
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) await save(null);
        }
      },
      markPasswordChanged: () => save({ ...session, user: { ...session.user, must_change_password: false } }),
      logout: () => save(null),
    }),
    [ready, session, save],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Fetches with the signed-in token; returns { data, loading, error, reload }. A 401 signs out. */
export function useApi(path, params, deps = []) {
  const { token, logout } = useAuth();
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const key = JSON.stringify(params ?? null);

  const reload = useCallback(async () => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      setState({ data: await api(path, { token, params }), loading: false, error: null });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) logout();
      setState({ data: null, loading: false, error: err });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, token, key, ...deps]);

  useEffect(() => {
    reload();
  }, [reload]);
  return { ...state, reload };
}
