const { test } = require("node:test");
const assert = require("node:assert/strict");
const { mapWorkoutPlanToDays } = require("../src/data/api-mappers.ts");

test("separates loaded, bodyweight, timed and rest entries", () => {
  const item = (name, equipment, prescription_kind, extra = {}) => ({
    id: name, exercise_id: name, prescription_kind, exercises: { name, equipment }, ...extra,
  });
  const week = mapWorkoutPlanToDays({ workout_days: [{
    id: "session", weekday: "tuesday", title: "Treino",
    workout_day_exercises: [
      item("Remada cavalinho", "landmine", "repetitions", { min_reps: 8, max_reps: 12 }),
      item("Flexão declinada", "bodyweight", "repetitions"),
      item("Prancha", "bodyweight", "repetitions"),
      item("Esteira", "treadmill", "duration", { duration_minutes: 15 }),
    ],
  }] });
  assert.equal(week[0].status, "rest");
  assert.equal(week[0].exercises.length, 0);
  assert.deepEqual(week[1].exercises.map((exercise) => [exercise.logMetric, exercise.canAddLoad]), [
    ["load", false], ["reps", true], ["time", true], ["time", false],
  ]);
  assert.equal(week[1].exercises[0].reps, "8-12");
  assert.equal(week[1].exercises[3].durationMinutes, 15);
});

test("uses added load for pull-ups while keeping bands, holds and support benches distinct", () => {
  const cases = [
    ["Barra fixa supinada", "pull_up_bar", "vertical_pull", "load", false, true],
    ["Barra fixa pronada", "pull_up_bar", "vertical_pull", "load", false, true],
    ["Barra fixa assistida", "assisted_pull_up_machine", "vertical_pull", "load", false, false],
    ["Remada cavalinho", "landmine", "horizontal_pull", "load", false, false],
    ["Arnold press", "dumbbell", "vertical_push", "load", false, false],
    ["Triceps acima da cabeca no cabo", "cable_station", "elbow_extension", "load", false, false],
    ["Band pull-apart", "resistance_band", "horizontal_abduction", "reps", false, false],
    ["Flexao declinada", "bodyweight", "horizontal_push", "reps", true, false],
    ["Prancha lateral", "bodyweight", "anti_lateral_flexion", "time", true, false],
    ["Prancha com toque", "bodyweight", "anti_rotation", "reps", true, false],
    ["L-sit", "dip_station", "isometric", "time", true, false],
    ["Elevacao de pernas suspenso", "pull_up_bar", "hip_flexion", "reps", true, false],
    ["Extensao lombar", "back_extension_machine", "hip_hinge", "reps", true, false],
    ["Glute ham raise", "back_extension_machine", "knee_flexion", "reps", true, false],
    ["Salto na caixa", "plyo_box", "jump", "reps", false, false],
  ];
  const [day] = mapWorkoutPlanToDays({ workout_days: [{
    id: "session", weekday: "monday", title: "Treino",
    workout_day_exercises: cases.map(([name, equipment, movement_pattern]) => ({
      id: name, exercise_id: name, prescription_kind: "repetitions",
      exercises: { name, equipment, movement_pattern },
    })),
  }] });
  for (const [index, [name, , , metric, canAddLoad, loadIsAdded]] of cases.entries()) {
    const actual = day.exercises[index];
    assert.deepEqual([actual.logMetric, actual.canAddLoad, actual.loadIsAdded],
      [metric, canAddLoad, loadIsAdded], name);
  }
});

test("a mudança pontual aparece na data de destino e a origem vira descanso", () => {
  const plan = { start_date: "2026-11-09", end_date: null, workout_days: [{
    id: "superiores", weekday: "thursday", title: "Superiores",
    workout_day_exercises: [],
  }] };
  const dates = Array.from({ length: 7 }, (_, index) => "2026-11-" + String(9 + index).padStart(2, "0"));
  const changes = [
    { activity_date: "2026-11-12", activity_type: "rest", workout_day_id: null },
    { activity_date: "2026-11-13", activity_type: "resistance", workout_day_id: "superiores" },
  ];
  const changed = mapWorkoutPlanToDays(plan, { dates, overrides: changes });
  assert.equal(changed[3].status, "rest");
  assert.equal(changed[4].title, "Superiores");
  assert.equal(changed[4].id, "superiores");
  const restored = mapWorkoutPlanToDays(plan, { dates, overrides: [] });
  assert.equal(restored[3].id, "superiores");
  assert.equal(restored[4].status, "rest");
});
