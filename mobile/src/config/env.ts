const trimTrailingSlash = (value: string | undefined) =>
  value?.trim().replace(/\/+$/, "") ?? "";

export const env = {
  supabaseUrl: trimTrailingSlash(process.env.EXPO_PUBLIC_SUPABASE_URL),
  supabaseAnonKey: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY?.trim() ?? "",
  apiUrl: trimTrailingSlash(process.env.EXPO_PUBLIC_API_URL),
};

export const hasSupabaseConfig = Boolean(
  env.supabaseUrl && env.supabaseAnonKey,
);

export const hasApiConfig = Boolean(env.apiUrl);
