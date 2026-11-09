export type SignupInput = {
  name: string;
  email: string;
  password: string;
  birthDate: string;
};

export function formatBirthDate(value: string) {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export function parseBirthDate(value: string, today = new Date()) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;
  const [, dayText, monthText, yearText] = match;
  const day = Number(dayText);
  const month = Number(monthText);
  const year = Number(yearText);
  const date = new Date(year, month - 1, day);
  const currentDay = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );
  if (
    year < 1900 ||
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day ||
    date > currentDay
  )
    return null;
  return `${yearText}-${monthText}-${dayText}`;
}

type SignupValidation =
  | { ok: true; name: string; email: string; birthDate?: string }
  | { ok: false; field: keyof SignupInput; message: string };

export function validateSignup(
  input: SignupInput,
  today = new Date(),
): SignupValidation {
  const name = input.name.trim();
  if (name.length < 2 || name.length > 120) {
    return {
      ok: false,
      field: "name",
      message: "Informe seu nome, entre 2 e 120 caracteres.",
    };
  }
  const email = input.email.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return { ok: false, field: "email", message: "Informe um e-mail válido." };
  }
  const birthDate = input.birthDate.trim()
    ? parseBirthDate(input.birthDate, today)
    : undefined;
  if (birthDate === null) {
    return {
      ok: false,
      field: "birthDate",
      message:
        "Confira a data de nascimento. Use dia, mês e ano, sem uma data futura.",
    };
  }
  if (input.password.length < 6 || !input.password.trim()) {
    return {
      ok: false,
      field: "password",
      message: "Use uma senha com pelo menos 6 caracteres.",
    };
  }
  return { ok: true, name, email, birthDate };
}
