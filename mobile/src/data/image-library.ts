import type { ImageSourcePropType } from "react-native";

import type { ImagePreferences } from "@/context/image-preferences-context";

export type WorkoutImageCategory =
  | "back"
  | "cardio"
  | "chest"
  | "fullBody"
  | "legs"
  | "preparation"
  | "recovery"
  | "shoulders";

type ImagePerson = "man" | "neutral" | "woman";
type ImageBodyType = "fitness" | "muscular" | "neutral";

export type CatalogImage = {
  id: string;
  source: ImageSourcePropType;
  person: ImagePerson;
  bodyType: ImageBodyType;
};

const image = (
  id: string,
  source: ImageSourcePropType,
  person: ImagePerson,
  bodyType: ImageBodyType,
): CatalogImage => ({ id, source, person, bodyType });

export const workoutImageLibrary: Record<WorkoutImageCategory, CatalogImage[]> =
  {
    chest: [
      image(
        "chest-classic",
        require("@/assets/images/workout-chest.png"),
        "man",
        "muscular",
      ),
      image(
        "chest-incline",
        require("@/assets/images/workout-chest-incline-man.png"),
        "man",
        "fitness",
      ),
      image(
        "chest-incline-black",
        require("@/assets/images/workout-chest-incline-man-black.png"),
        "man",
        "fitness",
      ),
      image(
        "chest-press-south-asian",
        require("@/assets/images/workout-chest-press-woman-south-asian.png"),
        "woman",
        "fitness",
      ),
      image(
        "chest-press-black",
        require("@/assets/images/workout-chest-press-woman-black-short-hair.png"),
        "woman",
        "fitness",
      ),
      image(
        "chest-dips-middle-eastern",
        require("@/assets/images/workout-chest-dips-man-middle-eastern.png"),
        "man",
        "muscular",
      ),
    ],
    legs: [
      image(
        "legs-classic",
        require("@/assets/images/workout-legs.png"),
        "man",
        "muscular",
      ),
      image(
        "legs-back-squat",
        require("@/assets/images/workout-legs-squat-man.png"),
        "man",
        "fitness",
      ),
      image(
        "legs-front-squat-black",
        require("@/assets/images/workout-legs-front-squat-woman-black.png"),
        "woman",
        "fitness",
      ),
      image(
        "legs-hack-squat-east-asian",
        require("@/assets/images/workout-legs-hack-squat-man-east-asian.png"),
        "man",
        "muscular",
      ),
      image(
        "legs-split-squat-east-asian",
        require("@/assets/images/workout-legs-split-squat-woman-east-asian.png"),
        "woman",
        "muscular",
      ),
      image(
        "legs-press-black-bald",
        require("@/assets/images/workout-legs-press-man-black-bald.png"),
        "man",
        "fitness",
      ),
    ],
    back: [
      image(
        "back-classic",
        require("@/assets/images/old-school-gym.png"),
        "man",
        "fitness",
      ),
      image(
        "back-row",
        require("@/assets/images/workout-back-row-man.png"),
        "man",
        "fitness",
      ),
      image(
        "back-pullup",
        require("@/assets/images/workout-back-pullup-man.png"),
        "man",
        "fitness",
      ),
      image(
        "back-row-black-woman",
        require("@/assets/images/workout-back-row-woman-black.png"),
        "woman",
        "fitness",
      ),
      image(
        "back-pulldown-black-bald",
        require("@/assets/images/workout-back-pulldown-man-black-bald.png"),
        "man",
        "fitness",
      ),
      image(
        "back-pullup-bodybuilder",
        require("@/assets/images/workout-back-pullup-bodybuilder-black.png"),
        "man",
        "muscular",
      ),
      image(
        "back-row-latino",
        require("@/assets/images/workout-back-row-man-latino.png"),
        "man",
        "fitness",
      ),
      image(
        "back-cable-row-latina",
        require("@/assets/images/workout-back-cable-row-woman-latina.png"),
        "woman",
        "fitness",
      ),
      image(
        "back-tbar-row-south-asian",
        require("@/assets/images/workout-back-tbar-row-man-south-asian.png"),
        "man",
        "muscular",
      ),
    ],
    shoulders: [
      image(
        "shoulders-classic",
        require("@/assets/images/workout-shoulders.png"),
        "man",
        "muscular",
      ),
      image(
        "shoulders-press",
        require("@/assets/images/workout-shoulders-press-man.png"),
        "man",
        "fitness",
      ),
      image(
        "shoulders-press-asian-woman",
        require("@/assets/images/workout-shoulders-press-woman-asian.png"),
        "woman",
        "fitness",
      ),
      image(
        "shoulders-raise-black-locs",
        require("@/assets/images/workout-shoulders-raise-man-black-locs.png"),
        "man",
        "fitness",
      ),
      image(
        "shoulders-press-red-hair",
        require("@/assets/images/workout-shoulders-press-woman-red-hair.png"),
        "woman",
        "muscular",
      ),
      image(
        "shoulders-face-pull-east-asian",
        require("@/assets/images/workout-shoulders-face-pull-man-east-asian.png"),
        "man",
        "fitness",
      ),
    ],
    preparation: [
      image(
        "prepare-classic",
        require("@/assets/images/workout-prepare.png"),
        "neutral",
        "neutral",
      ),
      image(
        "prepare-wraps",
        require("@/assets/images/workout-prepare-wraps-neutral.png"),
        "neutral",
        "neutral",
      ),
      image(
        "prepare-bench",
        require("@/assets/images/account-bench-gear.png"),
        "neutral",
        "neutral",
      ),
    ],
    fullBody: [
      image(
        "full-body-classic",
        require("@/assets/images/workout-full-body.png"),
        "man",
        "fitness",
      ),
      image(
        "full-body-carry",
        require("@/assets/images/workout-full-body-carry-man.png"),
        "man",
        "fitness",
      ),
      image(
        "full-body-ropes-latina",
        require("@/assets/images/workout-full-body-ropes-woman-latina.png"),
        "woman",
        "fitness",
      ),
      image(
        "full-body-deadlift-bald",
        require("@/assets/images/workout-full-body-deadlift-man-bald.png"),
        "man",
        "fitness",
      ),
      image(
        "full-body-deadlift-bodybuilder",
        require("@/assets/images/workout-full-body-deadlift-bodybuilder-bald.png"),
        "man",
        "muscular",
      ),
      image(
        "full-body-kettlebell-middle-eastern",
        require("@/assets/images/workout-full-body-kettlebell-woman-middle-eastern.png"),
        "woman",
        "fitness",
      ),
      image(
        "full-body-sled-pacific-islander",
        require("@/assets/images/workout-full-body-sled-man-pacific-islander.png"),
        "man",
        "muscular",
      ),
    ],
    cardio: [
      image(
        "cardio-run-south-asian",
        require("@/assets/images/workout-cardio-run-woman-south-asian.png"),
        "woman",
        "fitness",
      ),
      image(
        "cardio-ropes-latina",
        require("@/assets/images/workout-full-body-ropes-woman-latina.png"),
        "woman",
        "fitness",
      ),
      image(
        "cardio-carry",
        require("@/assets/images/workout-full-body-carry-man.png"),
        "man",
        "fitness",
      ),
      image(
        "cardio-air-bike-black",
        require("@/assets/images/workout-cardio-air-bike-man-black.png"),
        "man",
        "fitness",
      ),
    ],
    recovery: [
      image(
        "recovery-classic",
        require("@/assets/images/workout-recovery.png"),
        "neutral",
        "neutral",
      ),
      image(
        "recovery-stretch-woman",
        require("@/assets/images/workout-recovery-stretch-woman.png"),
        "woman",
        "fitness",
      ),
      image(
        "recovery-locker",
        require("@/assets/images/account-locker.png"),
        "neutral",
        "neutral",
      ),
      image(
        "recovery-mobility-east-asian",
        require("@/assets/images/workout-recovery-mobility-woman-east-asian.png"),
        "woman",
        "fitness",
      ),
    ],
  };

export const workoutCategoryByDayId: Record<string, WorkoutImageCategory> = {
  mon: "chest",
  tue: "legs",
  wed: "back",
  thu: "shoulders",
  fri: "preparation",
  sat: "fullBody",
  sun: "recovery",
};

export const dietImages: CatalogImage[] = [
  image(
    "diet-classic",
    require("@/assets/images/old-school-meal.png"),
    "neutral",
    "neutral",
  ),
  image(
    "diet-steak",
    require("@/assets/images/diet-steak-meal.png"),
    "neutral",
    "neutral",
  ),
  image(
    "diet-breakfast",
    require("@/assets/images/diet-breakfast-meal.png"),
    "neutral",
    "neutral",
  ),
  image(
    "diet-prep",
    require("@/assets/images/diet-prep.png"),
    "neutral",
    "neutral",
  ),
  image(
    "diet-swap",
    require("@/assets/images/diet-swap.png"),
    "neutral",
    "neutral",
  ),
  image(
    "diet-meal-prep-weekly",
    require("@/assets/images/diet-meal-prep-weekly.png"),
    "neutral",
    "neutral",
  ),
  image(
    "diet-cooking-salmon",
    require("@/assets/images/diet-cooking-salmon-woman.png"),
    "woman",
    "fitness",
  ),
  image(
    "diet-vegetarian-protein",
    require("@/assets/images/diet-vegetarian-protein.png"),
    "neutral",
    "neutral",
  ),
  image(
    "diet-market",
    require("@/assets/images/diet-market-man-east-asian.png"),
    "man",
    "fitness",
  ),
  image(
    "diet-post-workout-breakfast",
    require("@/assets/images/diet-post-workout-breakfast.png"),
    "neutral",
    "neutral",
  ),
];

export const accountImages: CatalogImage[] = [
  image(
    "account-locker",
    require("@/assets/images/account-locker.png"),
    "neutral",
    "neutral",
  ),
  image(
    "account-bench",
    require("@/assets/images/account-bench-gear.png"),
    "neutral",
    "neutral",
  ),
  image(
    "account-bag",
    require("@/assets/images/account-gym-bag.png"),
    "neutral",
    "neutral",
  ),
  image(
    "account-locker-mirror",
    require("@/assets/images/account-locker-mirror-woman.png"),
    "woman",
    "fitness",
  ),
  image(
    "account-training-history",
    require("@/assets/images/account-training-history-man.png"),
    "man",
    "fitness",
  ),
  image(
    "account-measurements",
    require("@/assets/images/account-measurements.png"),
    "neutral",
    "neutral",
  ),
  image(
    "account-weekly-planner",
    require("@/assets/images/account-weekly-planner.png"),
    "neutral",
    "neutral",
  ),
  image(
    "account-privacy-lock",
    require("@/assets/images/account-privacy-lock.png"),
    "neutral",
    "neutral",
  ),
  image(
    "account-progress-photo",
    require("@/assets/images/account-progress-photo.png"),
    "neutral",
    "fitness",
  ),
  image(
    "account-training-memories",
    require("@/assets/images/account-training-memories.png"),
    "neutral",
    "neutral",
  ),
];

export const coachImages: CatalogImage[] = [
  image(
    "coach-workspace",
    require("@/assets/images/coach-workspace.png"),
    "neutral",
    "neutral",
  ),
  image(
    "coach-voice-question",
    require("@/assets/images/coach-voice-question-woman.png"),
    "woman",
    "fitness",
  ),
  image(
    "coach-plan-adjustment",
    require("@/assets/images/coach-plan-adjustment.png"),
    "neutral",
    "neutral",
  ),
  image(
    "coach-training-journal",
    require("@/assets/images/coach-training-journal.png"),
    "neutral",
    "neutral",
  ),
  image(
    "coach-conversation-women",
    require("@/assets/images/coach-conversation-women.png"),
    "woman",
    "fitness",
  ),
  image(
    "coach-question",
    require("@/assets/images/coach-question-man-latino.png"),
    "man",
    "fitness",
  ),
  image(
    "coach-education-shoulder",
    require("@/assets/images/coach-education-shoulder.png"),
    "neutral",
    "fitness",
  ),
  image(
    "coach-nutrition-planning",
    require("@/assets/images/coach-nutrition-planning-woman.png"),
    "woman",
    "fitness",
  ),
  image(
    "coach-recovery-conversation",
    require("@/assets/images/coach-recovery-conversation.png"),
    "neutral",
    "fitness",
  ),
  image(
    "coach-progress-review",
    require("@/assets/images/coach-progress-review.png"),
    "neutral",
    "neutral",
  ),
];

function hash(value: string) {
  return [...value].reduce(
    (total, character) => (total * 31 + character.charCodeAt(0)) >>> 0,
    0,
  );
}

function weekSeed(date: Date) {
  const utcDate = Date.UTC(
    date.getUTCFullYear(),
    date.getUTCMonth(),
    date.getUTCDate(),
  );
  return Math.floor(utcDate / 604_800_000);
}

function filterWithFallback(
  current: CatalogImage[],
  condition: (item: CatalogImage) => boolean,
  minimumResults: number,
) {
  const filtered = current.filter(condition);
  return filtered.length >= minimumResults ? filtered : current;
}

export function getPreferredImages(
  images: CatalogImage[],
  preferences: ImagePreferences,
  minimumResults = 2,
) {
  let result = images;

  if (preferences.people === "men") {
    result = filterWithFallback(
      result,
      (item) => item.person === "man" || item.person === "neutral",
      minimumResults,
    );
  } else if (preferences.people === "women") {
    result = filterWithFallback(
      result,
      (item) => item.person === "woman" || item.person === "neutral",
      minimumResults,
    );
  }

  if (preferences.bodyType !== "mixed") {
    result = filterWithFallback(
      result,
      (item) =>
        item.bodyType === preferences.bodyType || item.bodyType === "neutral",
      minimumResults,
    );
  }

  return result;
}

export function pickWeeklyImage(
  images: CatalogImage[],
  preferences: ImagePreferences,
  rotationKey: string,
  slot = 0,
  date = new Date(),
) {
  const eligible = getPreferredImages(images, preferences);
  const index = (weekSeed(date) + hash(rotationKey) + slot) % eligible.length;
  return eligible[index].source;
}
