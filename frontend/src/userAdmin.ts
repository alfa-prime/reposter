const temporaryPasswordAlphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%";

export function generateTemporaryPassword(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(20));
  return Array.from(
    bytes,
    (value) => temporaryPasswordAlphabet[value % temporaryPasswordAlphabet.length],
  ).join("");
}

export function toggleRoleCode(codes: string[], code: string): string[] {
  return codes.includes(code)
    ? codes.filter((item) => item !== code)
    : [...codes, code];
}
