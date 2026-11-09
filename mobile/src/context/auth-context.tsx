import type { Session, User } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { AppState, Platform } from "react-native";

import { hasSupabaseConfig } from "@/config/env";
import { supabase } from "@/lib/supabase";

type SignUpResult = { needsEmailConfirmation: boolean };

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  isLoading: boolean;
  isConfigured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (
    email: string,
    password: string,
    fullName?: string,
    birthDate?: string,
  ) => Promise<SignUpResult>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function requireSupabase() {
  if (!supabase) {
    throw new Error(
      "Supabase nao configurado. Preencha o arquivo mobile/.env.local.",
    );
  }
  return supabase;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(hasSupabaseConfig);

  useEffect(() => {
    const client = supabase;
    if (!client) return;

    let mounted = true;
    void client.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session);
      setIsLoading(false);
    });

    const { data: listener } = client.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession);
        setIsLoading(false);
      },
    );

    const appStateSubscription =
      Platform.OS === "web"
        ? null
        : AppState.addEventListener("change", (state) => {
            if (state === "active") void client.auth.startAutoRefresh();
            else void client.auth.stopAutoRefresh();
          });

    return () => {
      mounted = false;
      listener.subscription.unsubscribe();
      appStateSubscription?.remove();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const client = requireSupabase();
    const { error } = await client.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    if (error) throw error;
  }, []);

  const signUp = useCallback(
    async (
      email: string,
      password: string,
      fullName?: string,
      birthDate?: string,
    ) => {
      const client = requireSupabase();
      const { data, error } = await client.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            ...(fullName?.trim() ? { full_name: fullName.trim() } : {}),
            ...(birthDate ? { birth_date: birthDate } : {}),
          },
        },
      });
      if (error) throw error;
      return { needsEmailConfirmation: !data.session };
    },
    [],
  );

  const signOut = useCallback(async () => {
    const client = requireSupabase();
    const { error } = await client.auth.signOut();
    if (error) throw error;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      isLoading,
      isConfigured: hasSupabaseConfig,
      signIn,
      signUp,
      signOut,
    }),
    [isLoading, session, signIn, signOut, signUp],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context)
    throw new Error("useAuth deve ser usado dentro de AuthProvider.");
  return context;
}
