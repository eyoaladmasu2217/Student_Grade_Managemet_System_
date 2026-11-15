export type GradeTone = "excellent" | "good" | "fair" | "pass" | "risk" | "neutral";

export function gradeTone(letter: string | null | undefined): GradeTone {
  if (!letter) {
    return "neutral";
  }

  const code = letter.trim().toUpperCase();
  if (!code) {
    return "neutral";
  }

  if (code.startsWith("A")) {
    return "excellent";
  }
  if (code.startsWith("B")) {
    return "good";
  }
  if (code.startsWith("C")) {
    return "fair";
  }
  if (code.startsWith("D")) {
    return "pass";
  }
  return "risk";
}

export function clampPercentage(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(100, Math.max(0, value));
}
