export function localDateOnly(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export const weekdaysFromSunday = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
] as const;

export const mondayWeekIndex = (date: Date) => (date.getDay() + 6) % 7;

export function addCalendarDays(date: Date, days: number) {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

export function mondayWeekDates(date: Date) {
  const monday = addCalendarDays(date, -mondayWeekIndex(date));
  return Array.from({ length: 7 }, (_, index) =>
    localDateOnly(addCalendarDays(monday, index)),
  );
}

export function calendarDayIndex(date: Date) {
  const day = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.floor(day / 86_400_000);
}
