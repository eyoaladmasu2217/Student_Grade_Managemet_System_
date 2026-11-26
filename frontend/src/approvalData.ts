import {
  apiRequest,
  CorrectionReasonCode,
  GradeChangeEvent,
  GradeCorrection,
  jsonBody,
  Section,
} from "./api";

type Request = typeof apiRequest;

export interface ApprovalData {
  requests: GradeCorrection[];
  auditTrail: GradeChangeEvent[];
}

export const reasonCodeLabels: Record<CorrectionReasonCode, string> = {
  grading_error: "Grading error",
  misgraded_work: "Misgraded work",
  data_entry: "Data-entry mistake",
  retake: "Approved retake",
  other: "Other reason",
};

export async function loadApprovalData(
  sections: Section[],
  request: Request = apiRequest,
): Promise<ApprovalData> {
  const [requests, trails] = await Promise.all([
    request<GradeCorrection[]>("/api/grade-change-requests?status=pending"),
    Promise.all(
      sections.map((section) =>
        request<GradeChangeEvent[]>(`/api/sections/${section.id}/audit-trail`),
      ),
    ),
  ]);
  const auditTrail = trails
    .flat()
    .sort((left, right) => Date.parse(right.occurred_at) - Date.parse(left.occurred_at));
  return { requests, auditTrail };
}

export async function reviewGradeChange(
  correctionId: number,
  decision: "approve" | "reject",
  note: string,
  request: Request = apiRequest,
): Promise<GradeCorrection> {
  return request<GradeCorrection>(
    `/api/grade-change-requests/${correctionId}/${decision}`,
    { method: "POST", body: jsonBody({ note }) },
  );
}
