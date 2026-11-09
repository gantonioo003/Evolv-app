import {
  createContext,
  useContext,
  useEffect,
  useState,
  type PropsWithChildren,
} from "react";
import { AccessibilityInfo, Platform } from "react-native";

const ReducedMotionContext = createContext(true);

export function MotionProvider({ children }: PropsWithChildren) {
  const [reducedMotion, setReducedMotion] = useState(true);

  useEffect(() => {
    if (Platform.OS === "web" && typeof globalThis.matchMedia === "function") {
      const preference = globalThis.matchMedia(
        "(prefers-reduced-motion: reduce)",
      );
      const update = () => setReducedMotion(preference.matches);
      update();
      preference.addEventListener("change", update);
      return () => preference.removeEventListener("change", update);
    }

    let active = true;
    void AccessibilityInfo.isReduceMotionEnabled()
      .then((enabled) => {
        if (active) setReducedMotion(enabled);
      })
      .catch(() => undefined);
    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      setReducedMotion,
    );
    return () => {
      active = false;
      subscription.remove();
    };
  }, []);

  return (
    <ReducedMotionContext.Provider value={reducedMotion}>
      {children}
    </ReducedMotionContext.Provider>
  );
}

export function useReducedMotion() {
  return useContext(ReducedMotionContext);
}
