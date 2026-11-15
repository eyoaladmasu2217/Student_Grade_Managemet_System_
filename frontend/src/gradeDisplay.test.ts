import { describe, expect, it } from "vitest";
import { clampPercentage, gradeTone } from "./gradeDisplay";

describe("gradeTone", () => {
  it("maps letter grades to visual tones", () => {
    expect(gradeTone("A")).toBe("excellent");
    expect(gradeTone("B+")).toBe("good");
    expect(gradeTone("C-")).toBe("fair");
    expect(gradeTone("D")).toBe("pass");
    expect(gradeTone("F")).toBe("risk");
  });

  it("treats missing grades as neutral", () => {
    expect(gradeTone(null)).toBe("neutral");
    expect(gradeTone(undefined)).toBe("neutral");
    expect(gradeTone("  ")).toBe("neutral");
  });
});

describe("clampPercentage", () => {
  it("keeps percentages within the meter range", () => {
    expect(clampPercentage(-4)).toBe(0);
    expect(clampPercentage(42.5)).toBe(42.5);
    expect(clampPercentage(140)).toBe(100);
  });
});
