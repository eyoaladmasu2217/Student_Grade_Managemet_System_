import {
  GradeBand,
  SimulationAssessment,
  SimulationCategory,
} from "./api";

export type SimulationScenario = Record<number, number | null>;

export interface ProjectedGrade {
  weighted_points: number;
  graded_weight: number;
  current_percentage: number | null;
  projected_percentage: number | null;
  complete: boolean;
}

export interface TargetScore {
  required_points: number | null;
  required_percentage: number | null;
  maximum_percentage: number | null;
  attainable: boolean;
  reason: "ok" | "unreachable" | "invalid-target" | "weights-incomplete" | "missing-assessment";
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

function effectivePoints(
  assessment: SimulationAssessment,
  scenario: SimulationScenario,
): number | null {
  if (Object.prototype.hasOwnProperty.call(scenario, assessment.id)) {
    const value = scenario[assessment.id];
    if (value === null || !Number.isFinite(value)) return null;
    return Math.min(Math.max(value, 0), assessment.max_points);
  }
  if (assessment.points === null || !Number.isFinite(assessment.points)) {
    return null;
  }
  return Math.min(Math.max(assessment.points, 0), assessment.max_points);
}

export function projectGrade(
  categories: SimulationCategory[],
  assessments: SimulationAssessment[],
  scenario: SimulationScenario = {},
): ProjectedGrade {
  const totals = new Map<number, { earned: number; max: number; scored: number; total: number }>();
  for (const category of categories) {
    totals.set(category.id, { earned: 0, max: 0, scored: 0, total: 0 });
  }

  for (const assessment of assessments) {
    const total = totals.get(assessment.category_id);
    if (!total) continue;
    total.total += 1;
    const points = effectivePoints(assessment, scenario);
    if (points === null) continue;
    total.earned += points;
    total.max += assessment.max_points;
    total.scored += 1;
  }

  let weightedPoints = 0;
  let gradedWeight = 0;
  const totalWeight = categories.reduce((sum, category) => sum + category.weight, 0);
  let allScored = categories.length > 0;
  for (const category of categories) {
    const total = totals.get(category.id);
    if (!total || total.scored === 0 || total.max <= 0) {
      allScored = false;
      continue;
    }
    weightedPoints += (total.earned / total.max) * category.weight;
    gradedWeight += category.weight;
    if (total.scored !== total.total) allScored = false;
  }

  const complete =
    allScored && Math.abs(totalWeight - 100) < 0.000001 && gradedWeight > 0;
  return {
    weighted_points: round(weightedPoints),
    graded_weight: round(gradedWeight),
    current_percentage: gradedWeight > 0 ? round((weightedPoints / gradedWeight) * 100) : null,
    projected_percentage: complete ? round(weightedPoints) : null,
    complete,
  };
}

export function scoreNeededForTarget(
  categories: SimulationCategory[],
  assessments: SimulationAssessment[],
  assessmentId: number,
  targetPercentage: number,
  scenario: SimulationScenario = {},
): TargetScore {
  const missing: TargetScore = {
    required_points: null,
    required_percentage: null,
    maximum_percentage: null,
    attainable: false,
    reason: "missing-assessment",
  };
  const assessment = assessments.find((item) => item.id === assessmentId);
  if (!assessment) return missing;
  const category = categories.find((item) => item.id === assessment.category_id);
  if (!category || category.weight <= 0) return missing;
  if (!Number.isFinite(targetPercentage) || targetPercentage < 0 || targetPercentage > 100) {
    return { ...missing, reason: "invalid-target" };
  }
  const totalWeight = categories.reduce((sum, item) => sum + item.weight, 0);
  if (Math.abs(totalWeight - 100) >= 0.000001) {
    return { ...missing, reason: "weights-incomplete" };
  }

  const withoutTarget = projectGrade(categories, assessments, {
    ...scenario,
    [assessmentId]: null,
  });
  let otherMax = 0;
  let otherEarned = 0;
  for (const item of assessments) {
    if (item.id === assessmentId || item.category_id !== assessment.category_id) continue;
    const points = effectivePoints(item, scenario);
    if (points === null) continue;
    otherMax += item.max_points;
    otherEarned += points;
  }

  const totalMax = otherMax + assessment.max_points;
  const required =
    ((targetPercentage - withoutTarget.weighted_points) * totalMax) / category.weight -
    otherEarned;
  const maximum =
    withoutTarget.weighted_points +
    (category.weight * (otherEarned + assessment.max_points)) / totalMax;
  const attainable = required <= assessment.max_points + 0.005;
  const minimumPoints = Math.max(0, round(required));

  return {
    required_points: attainable ? minimumPoints : null,
    required_percentage: attainable
      ? round((minimumPoints / assessment.max_points) * 100)
      : null,
    maximum_percentage: round(Math.min(100, maximum)),
    attainable,
    reason: attainable ? "ok" : "unreachable",
  };
}

export function letterForPercentage(
  bands: GradeBand[],
  percentage: number | null,
): string {
  if (percentage === null) return "—";
  const sorted = [...bands].sort(
    (left, right) => right.minimum_percentage - left.minimum_percentage,
  );
  return sorted.find((band) => percentage >= band.minimum_percentage)?.code ?? "—";
}
