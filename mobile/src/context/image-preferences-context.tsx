import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

export type PeoplePreference = "automatic" | "men" | "women";
export type BodyTypePreference = "fitness" | "mixed" | "muscular";

export type ImagePreferences = {
  people: PeoplePreference;
  bodyType: BodyTypePreference;
};

type ImagePreferencesContextValue = ImagePreferences & {
  setPeople: (value: PeoplePreference) => void;
  setBodyType: (value: BodyTypePreference) => void;
};

type StoredImagePreferences = {
  bodyType?: unknown;
  people?: unknown;
  physique?: unknown;
};

const storageKey = "@evolv/image-preferences";
const defaults: ImagePreferences = {
  people: "automatic",
  bodyType: "mixed",
};

const ImagePreferencesContext =
  createContext<ImagePreferencesContextValue | null>(null);

function normalizePeople(value: unknown): PeoplePreference {
  return value === "men" || value === "women" ? value : "automatic";
}

function normalizeBodyType(value: unknown): BodyTypePreference {
  if (value === "fitness" || value === "muscular") return value;
  if (value === "athletic") return "fitness";
  if (value === "bodybuilder") return "muscular";
  return "mixed";
}

export function ImagePreferencesProvider({ children }: PropsWithChildren) {
  const [preferences, setPreferences] = useState<ImagePreferences>(defaults);

  useEffect(() => {
    AsyncStorage.getItem(storageKey)
      .then((saved) => {
        if (!saved) return;
        const stored = JSON.parse(saved) as StoredImagePreferences;
        setPreferences({
          people: normalizePeople(stored.people),
          bodyType: normalizeBodyType(stored.bodyType ?? stored.physique),
        });
      })
      .catch(() => undefined);
  }, []);

  function update(next: Partial<ImagePreferences>) {
    setPreferences((current) => {
      const value = { ...current, ...next };
      AsyncStorage.setItem(storageKey, JSON.stringify(value)).catch(
        () => undefined,
      );
      return value;
    });
  }

  const value = useMemo<ImagePreferencesContextValue>(
    () => ({
      ...preferences,
      setPeople: (people) => update({ people }),
      setBodyType: (bodyType) => update({ bodyType }),
    }),
    [preferences],
  );

  return (
    <ImagePreferencesContext.Provider value={value}>
      {children}
    </ImagePreferencesContext.Provider>
  );
}

export function useImagePreferences() {
  const context = useContext(ImagePreferencesContext);
  if (!context)
    throw new Error(
      "useImagePreferences must be used inside ImagePreferencesProvider",
    );
  return context;
}
