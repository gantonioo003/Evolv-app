import type { ImageSourcePropType } from "react-native";

export const authPhotos: readonly ImageSourcePropType[] = [
  require("@/assets/images/auth-selected-01.jpg"),
  require("@/assets/images/auth-selected-02.jpg"),
  require("@/assets/images/auth-selected-03.jpg"),
  require("@/assets/images/auth-selected-04.jpg"),
  require("@/assets/images/auth-selected-05.jpg"),
  require("@/assets/images/auth-selected-06.jpg"),
  require("@/assets/images/auth-selected-07.jpg"),
  require("@/assets/images/auth-selected-08.jpg"),
];

export function nextAuthPhotoIndex(saved: string | null): number {
  if (saved === null || !/^\d+$/.test(saved)) return 0;
  const previous = Number(saved);
  if (!Number.isSafeInteger(previous) || previous >= authPhotos.length)
    return 0;
  return (previous + 1) % authPhotos.length;
}
