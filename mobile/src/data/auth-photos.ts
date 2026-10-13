import type { ImageSourcePropType } from "react-native";

export const authPhotos: readonly ImageSourcePropType[] = [
  require("@/assets/images/auth-training.jpg"),
  require("@/assets/images/auth-training-02.jpg"),
  require("@/assets/images/auth-training-03.jpg"),
  require("@/assets/images/auth-training-04.jpg"),
  require("@/assets/images/auth-training-05.jpg"),
  require("@/assets/images/auth-training-06.jpg"),
  require("@/assets/images/auth-training-07.jpg"),
  require("@/assets/images/auth-training-08.jpg"),
  require("@/assets/images/auth-training-09.jpg"),
  require("@/assets/images/auth-training-10.jpg"),
];

export function nextAuthPhotoIndex(saved: string | null): number {
  if (saved === null || !/^\d+$/.test(saved)) return 0;
  const previous = Number(saved);
  if (!Number.isSafeInteger(previous) || previous >= authPhotos.length)
    return 0;
  return (previous + 1) % authPhotos.length;
}
