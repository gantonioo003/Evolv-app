import { useState, type ComponentPropsWithRef } from "react";
import {
  Animated,
  Platform,
  Pressable,
  StyleSheet,
} from "react-native";

import { useReducedMotion } from "@/context/motion-context";

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

type TouchFeedbackProps = ComponentPropsWithRef<typeof Pressable> & {
  pressScale?: number;
};

export function TouchFeedback({
  children,
  onPressIn,
  onPressOut,
  pressScale = 0.98,
  style,
  ...props
}: TouchFeedbackProps) {
  const reducedMotion = useReducedMotion();
  const [progress] = useState(() => new Animated.Value(0));
  const [pressed, setPressed] = useState(false);
  const resolvedStyle =
    typeof style === "function" ? style({ pressed }) : style;
  const originalTransform = StyleSheet.flatten(resolvedStyle)?.transform;

  function animate(toValue: number) {
    progress.stopAnimation();
    if (reducedMotion) {
      progress.setValue(0);
      return;
    }
    Animated.spring(progress, {
      toValue,
      damping: 20,
      stiffness: 380,
      mass: 0.6,
      useNativeDriver: Platform.OS !== "web",
    }).start();
  }

  return (
    <AnimatedPressable
      {...props}
      onPressIn={(event) => {
        setPressed(true);
        animate(1);
        onPressIn?.(event);
      }}
      onPressOut={(event) => {
        setPressed(false);
        animate(0);
        onPressOut?.(event);
      }}
      style={[
        resolvedStyle,
        {
          transform: [
            ...(Array.isArray(originalTransform) ? originalTransform : []),
            {
              scale: progress.interpolate({
                inputRange: [0, 1],
                outputRange: [1, pressScale],
              }),
            },
          ],
        },
      ]}
    >
      {children}
    </AnimatedPressable>
  );
}
