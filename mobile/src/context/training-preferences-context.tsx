import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { Platform } from 'react-native';

import {
  defaultTrainingFocuses,
  defaultTrainingModalities,
  trainingFocuses,
  trainingModalities,
} from '@/data/training-options';

const MODALITIES_KEY = '@evolv/training-modalities';
const FOCUSES_KEY = '@evolv/training-focuses';
const validModalityIds = new Set(trainingModalities.map((option) => option.id));
const validFocusIds = new Set(trainingFocuses.map((option) => option.id));

type TrainingPreferencesContextValue = {
  selectedModalityIds: string[];
  selectedFocusIds: string[];
  toggleModality: (id: string) => void;
  toggleFocus: (id: string) => void;
};

const TrainingPreferencesContext = createContext<TrainingPreferencesContextValue | null>(null);

async function readSelection(key: string) {
  const raw = Platform.OS === 'web' && typeof globalThis.localStorage !== 'undefined'
    ? globalThis.localStorage.getItem(key)
    : await AsyncStorage.getItem(key);

  if (!raw) return null;

  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.every((item) => typeof item === 'string') ? parsed : null;
  } catch {
    return null;
  }
}

async function saveSelection(key: string, values: string[]) {
  const serialized = JSON.stringify(values);

  if (Platform.OS === 'web' && typeof globalThis.localStorage !== 'undefined') {
    globalThis.localStorage.setItem(key, serialized);
    return;
  }

  await AsyncStorage.setItem(key, serialized);
}

function toggleValue(current: string[], id: string) {
  return current.includes(id) ? current.filter((value) => value !== id) : [...current, id];
}

export function TrainingPreferencesProvider({ children }: PropsWithChildren) {
  const [selectedModalityIds, setSelectedModalityIds] = useState(defaultTrainingModalities);
  const [selectedFocusIds, setSelectedFocusIds] = useState(defaultTrainingFocuses);

  useEffect(() => {
    let active = true;

    void Promise.all([readSelection(MODALITIES_KEY), readSelection(FOCUSES_KEY)]).then(([savedModalities, savedFocuses]) => {
      if (!active) return;

      if (savedModalities) setSelectedModalityIds(savedModalities.filter((id) => validModalityIds.has(id)));
      if (savedFocuses) setSelectedFocusIds(savedFocuses.filter((id) => validFocusIds.has(id)));
    });

    return () => {
      active = false;
    };
  }, []);

  const toggleModality = useCallback((id: string) => {
    setSelectedModalityIds((current) => {
      const next = toggleValue(current, id);
      void saveSelection(MODALITIES_KEY, next);
      return next;
    });
  }, []);

  const toggleFocus = useCallback((id: string) => {
    setSelectedFocusIds((current) => {
      const next = toggleValue(current, id);
      void saveSelection(FOCUSES_KEY, next);
      return next;
    });
  }, []);

  const value = useMemo<TrainingPreferencesContextValue>(() => ({
    selectedModalityIds,
    selectedFocusIds,
    toggleModality,
    toggleFocus,
  }), [selectedFocusIds, selectedModalityIds, toggleFocus, toggleModality]);

  return <TrainingPreferencesContext.Provider value={value}>{children}</TrainingPreferencesContext.Provider>;
}

export function useTrainingPreferences() {
  const context = useContext(TrainingPreferencesContext);
  if (!context) throw new Error('useTrainingPreferences must be used inside TrainingPreferencesProvider.');
  return context;
}
