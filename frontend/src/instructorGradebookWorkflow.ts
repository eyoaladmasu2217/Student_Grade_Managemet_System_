import {
  apiRequest,
  Category,
  Enrollment,
  Gradebook,
  GradeCorrection,
  jsonBody,
} from "./api";

type Request = typeof apiRequest;

export interface InstructorGradebookState {
  sectionId: string;
  gradebook: Gradebook | null;
  categories: Category[];
  roster: Enrollment[];
  corrections: GradeCorrection[];
  loading: boolean;
  working: boolean;
  error: string;
  message: string;
  fieldErrors: Record<string, string>;
}

const emptyState: InstructorGradebookState = {
  sectionId: "",
  gradebook: null,
  categories: [],
  roster: [],
  corrections: [],
  loading: false,
  working: false,
  error: "",
  message: "",
  fieldErrors: {},
};

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

export function createInstructorGradebookWorkflow(
  request: Request = apiRequest,
) {
  let state = emptyState;
  let loadVersion = 0;
  const listeners = new Set<() => void>();

  function update(patch: Partial<InstructorGradebookState>) {
    state = { ...state, ...patch };
    listeners.forEach((listener) => listener());
  }

  async function loadSelectedSection(): Promise<void> {
    const sectionId = state.sectionId;
    if (!sectionId) return;

    const version = ++loadVersion;
    update({ loading: true, error: "" });
    try {
      const section = Number(sectionId);
      const [gradebook, categories, roster, corrections] = await Promise.all([
        request<Gradebook>(`/api/sections/${section}/gradebook`),
        request<Category[]>(`/api/sections/${section}/categories`),
        request<Enrollment[]>(`/api/sections/${section}/enrollments`),
        request<GradeCorrection[]>(`/api/sections/${section}/corrections`),
      ]);
      if (version === loadVersion) {
        update({ gradebook, categories, roster, corrections });
      }
    } catch (error) {
      if (version === loadVersion) update({ error: messageOf(error) });
    } finally {
      if (version === loadVersion) update({ loading: false });
    }
  }

  async function write(
    action: () => Promise<unknown>,
    successMessage: string,
    fieldErrorKey = "",
  ): Promise<boolean> {
    update({
      error: "",
      message: "",
      working: true,
      fieldErrors: fieldErrorKey
        ? { ...state.fieldErrors, [fieldErrorKey]: "" }
        : state.fieldErrors,
    });
    try {
      await action();
      update({ message: successMessage });
      await loadSelectedSection();
      return true;
    } catch (error) {
      const message = messageOf(error);
      if (fieldErrorKey) {
        update({ fieldErrors: { ...state.fieldErrors, [fieldErrorKey]: message } });
      } else {
        update({ error: message });
      }
      return false;
    } finally {
      update({ working: false });
    }
  }

  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    async selectSection(sectionId: string) {
      loadVersion += 1;
      update({
        ...emptyState,
        sectionId,
        loading: Boolean(sectionId),
      });
      await loadSelectedSection();
    },
    refresh: loadSelectedSection,
    createCategory(name: string, weight: number) {
      if (!state.sectionId) return Promise.resolve(false);
      return write(
        () =>
          request(`/api/sections/${state.sectionId}/categories`, {
            method: "POST",
            body: jsonBody({ name, weight }),
          }),
        "Assessment category created.",
      );
    },
    createAssessment(
      categoryId: number,
      title: string,
      maxPoints: number,
      dueDate: string | null,
    ) {
      return write(
        () =>
          request(`/api/categories/${categoryId}/assessments`, {
            method: "POST",
            body: jsonBody({ title, max_points: maxPoints, due_date: dueDate }),
          }),
        "Assessment created.",
      );
    },
    saveCategoryWeight(categoryId: number, weight: number) {
      const key = `weight:${categoryId}`;
      return write(
        () =>
          request(`/api/categories/${categoryId}/weight`, {
            method: "PATCH",
            body: jsonBody({ weight }),
          }),
        "",
        key,
      );
    },
    saveScore(
      assessmentId: number,
      studentId: number,
      points: number,
      reason: string,
    ) {
      const key = `score:${assessmentId}:${studentId}`;
      const released = state.gradebook?.grades_released ?? false;
      const path = released
        ? `/api/assessments/${assessmentId}/scores/${studentId}/correction`
        : `/api/assessments/${assessmentId}/scores/${studentId}`;
      const payload = released ? { points, reason } : { points };
      return write(
        () => request(path, { method: "PUT", body: jsonBody(payload) }),
        "",
        key,
      );
    },
    releaseGrades() {
      if (!state.sectionId) return Promise.resolve(false);
      return write(
        () => request(`/api/sections/${state.sectionId}/release`, { method: "POST" }),
        "Final grades released to students.",
      );
    },
  };
}
