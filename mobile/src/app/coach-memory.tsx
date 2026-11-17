import { useEffect, useMemo, useState } from "react";
import { Redirect, useRouter } from "expo-router";
import { ArrowLeft } from "lucide-react-native";
import { Pressable, Switch, Text, View } from "react-native";

import { IllustrationThumbnail, AppScreen, PageHeader, Surface } from "@/components/ui";
import { artwork } from "@/data/illustrations";
import { useAuth } from "@/context/auth-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme } from "@/context/theme-context";
import { CoachApi } from "@/services/coach-api";

export default function CoachMemoryScreen() {
  const { session, isLoading } = useAuth();
  const { profile, updateProfile } = useEvolvData();
  const { palette } = useAppTheme();
  const router = useRouter();
  const token = session?.access_token;
  const api = useMemo(() => new CoachApi(token ?? ""), [token]);
  const [items, setItems] = useState<Awaited<ReturnType<CoachApi["memory"]>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    let active = true;
    setItems(null);
    void api.memory().then(
      (result) => { if (active) setItems(result); },
      () => { if (active) setError("Não foi possível carregar a memória."); },
    );
    return () => { active = false; };
  }, [api, token]);

  async function change(operation: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch {
      setError("Não foi possível salvar a alteração. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return null;
  if (!session) return <Redirect href="/login" />;

  return (
    <AppScreen header={<PageHeader eyebrow="Conta" title="Memória do Coach"
      actionIcon={ArrowLeft} actionLabel="Voltar" onAction={() => router.back()} />}>
      <Surface>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
          <IllustrationThumbnail source={artwork.coachMemory} />
          <View style={{ flex: 1, gap: 8 }}>
            <Text style={{ color: palette.text, fontWeight: "700" }}>Usar memória entre conversas</Text>
            <Text style={{ color: palette.muted }}>Guarde preferências dizendo “Lembre que prefiro treinar à noite”.</Text>
          </View>
          <Switch accessibilityLabel="Usar memória entre conversas" disabled={busy || !profile}
            value={profile?.coach_memory_enabled ?? false}
            onValueChange={(enabled) => void change(() => updateProfile({ coach_memory_enabled: enabled }))} />
        </View>
      </Surface>
      {error ? <Text accessibilityRole="alert" style={{ color: palette.text }}>{error}</Text> : null}
      {items?.length === 0 ? <Text style={{ color: palette.muted }}>Você ainda não tem itens salvos.</Text> : null}
      {items?.map((item) => (
        <Surface key={item.id}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
            <Text style={{ flex: 1, color: palette.text }}>{item.content}</Text>
            <Pressable accessibilityRole="button" disabled={busy} style={{ paddingVertical: 10 }} onPress={() => {
              void change(async () => {
                await api.forget(item.id);
                setItems((previous) => previous?.filter((saved) => saved.id !== item.id) ?? null);
              });
            }}>
              <Text style={{ color: palette.text, fontWeight: "700" }}>Esquecer</Text>
            </Pressable>
          </View>
        </Surface>
      ))}
    </AppScreen>
  );
}
