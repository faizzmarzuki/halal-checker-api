import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { login as apiLogin, me as apiMe, logout as apiLogout } from "../api/auth";
import { ensureApiKey } from "../api/keys";
import { readSession, saveSession, clearSession } from "./session";

type Status = "loading" | "authenticated" | "unauthenticated";

type AuthValue = {
  status: Status;
  email: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const s = await readSession();
      if (s.access) {
        setEmail(s.email);
        setStatus("authenticated");
      } else {
        setStatus("unauthenticated");
      }
    })();
  }, []);

  const signIn = useCallback(async (e: string, password: string) => {
    const tokens = await apiLogin(e, password);
    await saveSession({ access: tokens.access_token, refresh: tokens.refresh_token });
    const profile = await apiMe();
    await saveSession({ email: profile.email });
    await ensureApiKey();
    setEmail(profile.email);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    await clearSession();
    setEmail(null);
    setStatus("unauthenticated");
  }, []);

  return (
    <AuthContext.Provider value={{ status, email, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
