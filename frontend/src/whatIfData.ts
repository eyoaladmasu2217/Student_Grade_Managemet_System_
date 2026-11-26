import { apiRequest, Section, WhatIfSimulation } from "./api";

type Request = typeof apiRequest;

export async function loadSimulationSections(
  request: Request = apiRequest,
): Promise<Section[]> {
  return request<Section[]>("/api/enrollments/mine");
}

export async function loadWhatIfSimulation(
  sectionId: number,
  request: Request = apiRequest,
): Promise<WhatIfSimulation> {
  return request<WhatIfSimulation>(`/api/sections/${sectionId}/what-if`);
}
