"use client";

// Auth context: exposes the current session + user, and login/logout helpers.
// Token persistence lives in ./tokens; this hook makes it reactive and layers
// the /users/me profile on top via React Query.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, AuthExpiredError } from "./api";
import {
  clearTokens,
  getAccessToken,
  setTokens,
  subscribe,
} from "./tokens";
import type { Token, User } from "./types";

interface AuthContextValue {
  isAuthenticated: boolean;
  user: User | null;
  isLoadingUser: boolean;
  login: (token: Token) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  // Mirror the token store into React state so consumers re-render on change.
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setHasToken(Boolean(getAccessToken()));
    return subscribe(() => setHasToken(Boolean(getAccessToken())));
  }, []);

  const userQuery = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    enabled: hasToken,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  // A failed /me due to an unrecoverable session means the tokens are dead.
  useEffect(() => {
    if (userQuery.error instanceof AuthExpiredError) clearTokens();
  }, [userQuery.error]);

  const login = useCallback(
    (token: Token) => {
      setTokens(token);
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    [queryClient]
  );

  const logout = useCallback(() => {
    clearTokens();
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: hasToken,
      user: userQuery.data ?? null,
      isLoadingUser: hasToken && userQuery.isLoading,
      login,
      logout,
    }),
    [hasToken, userQuery.data, userQuery.isLoading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
