import { FormEvent, useEffect, useState, useSyncExternalStore } from "react";
import { apiRequest, Assessment, Category, Section } from "./api";
import {
  createInstructorGradebookWorkflow,
} from "./instructorGradebookWorkflow";

interface ScoreCellProps {
  assessment: Assessment;
  studentId: number;
  score: number | undefined;
  released: boolean;
  error: string;
  onSave: (assessmentId: number, studentId: number, points: number, reason: string) => Promise<boolean>;
}

interface WeightEditorProps {
  category: Category;
  error: string;
  onSave: (categoryId: number, weight: number) => Promise<boolean>;
}

function WeightEditor({ category, error, onSave }: WeightEditorProps) {
  const [weight, setWeight] = useState(String(category.weight));

  useEffect(() => {
    setWeight(String(category.weight));
  }, [category.weight]);

  async function saveWeight(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave(category.id, Number(weight));
  }

  return (
    <form className="weight-editor" onSubmit={saveWeight}>
      <label className="visually-hidden" htmlFor={`weight-${category.id}`}>
        {category.name} category weight
      </label>
      <input
        id={`weight-${category.id}`}
        type="number"
        min="0.1"
        max="100"
        step="0.1"
        value={weight}
        onChange={(event) => setWeight(event.target.value)}
        required
      />
      <button className="text-button" type="submit">Save weight</button>
      {error && <span className="cell-error" role="alert">{error}</span>}
    </form>
  );
}

function ScoreCell({
  assessment,
  studentId,
  score,
  released,
  error,
  onSave,
}: ScoreCellProps) {
  const [points, setPoints] = useState(score === undefined ? "" : String(score));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPoints(score === undefined ? "" : String(score));
  }, [score]);

  async function saveScore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      const saved = await onSave(
        assessment.id,
        studentId,
        Number(points),
        reason,
      );
      if (saved) setReason("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="score-cell" onSubmit={saveScore}>
      <label className="visually-hidden" htmlFor={`score-${assessment.id}-${studentId}`}>
        {assessment.title} score for student {studentId}
      </label>
      <input
        id={`score-${assessment.id}-${studentId}`}
        type="number"
        min="0"
        max={assessment.max_points}
        step="0.01"
        value={points}
        onChange={(event) => setPoints(event.target.value)}
        required
      />
      {released && (
        <input
          aria-label="Correction reason"
          placeholder="Reason for correction"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          minLength={8}
          required
        />
      )}
      <button className="text-button" type="submit" disabled={saving}>
        {saving ? "Saving..." : released ? "Correct" : "Save"}
      </button>
      {error && <span className="cell-error" role="alert">{error}</span>}
    </form>
  );
}

export default function InstructorDashboard() {
  const [workflow] = useState(() => createInstructorGradebookWorkflow());
  const workflowState = useSyncExternalStore(
    workflow.subscribe,
    workflow.getSnapshot,
    workflow.getSnapshot,
  );
  const [sections, setSections] = useState<Section[]>([]);
  const [sectionsLoading, setSectionsLoading] = useState(true);
  const [sectionId, setSectionId] = useState("");
  const [sectionError, setSectionError] = useState("");
  const { gradebook, categories, roster, corrections, error, message, working, fieldErrors } =
    workflowState;

  useEffect(() => {
    let active = true;
    setSectionsLoading(true);
    setSectionError("");
    apiRequest<Section[]>("/api/sections")
      .then((result) => {
        if (active) {
          setSections(result);
          setSectionId((current) => current || String(result[0]?.id ?? ""));
        }
      })
      .catch((loadError: unknown) => {
        if (active) {
          setSectionError(
            loadError instanceof Error
              ? loadError.message
              : "The request could not be completed.",
          );
        }
      })
      .finally(() => {
        if (active) {
          setSectionsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    void workflow.selectSection(sectionId);
  }, [sectionId, workflow]);

  async function createCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sectionId) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const saved = await workflow.createCategory(
      String(form.get("name") ?? ""),
      Number(form.get("weight")),
    );
    if (saved) formElement.reset();
  }

  async function createAssessment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const categoryId = Number(form.get("category_id"));
    const dueDate = String(form.get("due_date") ?? "");
    const saved = await workflow.createAssessment(
      categoryId,
      String(form.get("title") ?? ""),
      Number(form.get("max_points")),
      dueDate || null,
    );
    if (saved) formElement.reset();
  }

  const section = sections.find((item) => String(item.id) === sectionId);
  const canRelease =
    !!gradebook &&
    !gradebook.grades_released &&
    gradebook.students.length > 0 &&
    gradebook.students.every((student) => student.is_complete);

  return (
    <section
      className="dashboard-layout"
      aria-labelledby="instructor-title"
      aria-busy={sectionsLoading || workflowState.loading}
    >
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">INSTRUCTOR WORKSPACE</p>
          <h1 id="instructor-title">Course gradebooks</h1>
          <p className="welcome-copy">
            Set assessments, enter scores, and release completed course grades.
          </p>
        </div>
        {sections.length > 0 && (
          <label className="section-picker">
            Active section
            <select value={sectionId} onChange={(event) => setSectionId(event.target.value)}>
              {sections.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.course_code} · {item.section_code} · {item.term_name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {(error || sectionError) && (
        <p className="form-error dashboard-message" role="alert">{error || sectionError}</p>
      )}
      {message && <p className="success-message dashboard-message" role="status">{message}</p>}

      {sectionsLoading ? (
        <p className="empty-state" role="status" aria-live="polite">
          Loading assigned sections...
        </p>
      ) : !sectionId ? (
        <section className="panel empty-panel">
          <h2>No assigned sections</h2>
          <p>Your sections will appear here after an academic administrator assigns them.</p>
        </section>
      ) : (
        <>
          <section className="section-summary">
            <div>
              <p className="eyebrow">{section?.term_name ?? "COURSE SECTION"}</p>
              <h2>{section?.course_code} · {section?.course_title}</h2>
              <p className="panel-note">Section {section?.section_code}</p>
            </div>
            <div className={`release-badge ${gradebook?.grades_released ? "release-badge--released" : ""}`}>
              {gradebook?.grades_released ? "Grades released" : "Draft gradebook"}
            </div>
          </section>

          <div className="dashboard-grid">
            <article className="panel">
              <h2>Assessment categories</h2>
              {!gradebook?.grades_released && (
                <form className="inline-form" onSubmit={createCategory}>
                  <label>
                    Category
                    <input name="name" placeholder="Exams" required maxLength={80} />
                  </label>
                  <label>
                    Weight %
                    <input name="weight" type="number" min="0.1" max="100" step="0.1" required />
                  </label>
                  <button className="primary-button" disabled={working}>Add category</button>
                </form>
              )}
              <ul className="record-list">
                {categories.map((category) => (
                  <li key={category.id}>
                    <div className="category-info">
                      <strong>{category.name}</strong>
                      <span>{category.weight}% of final grade</span>
                    </div>
                    {!gradebook?.grades_released && (
                      <WeightEditor
                        category={category}
                        error={fieldErrors[`weight:${category.id}`] ?? ""}
                        onSave={workflow.saveCategoryWeight}
                      />
                    )}
                  </li>
                ))}
                {categories.length === 0 && (
                  <li className="empty-state">Add categories whose weights total 100%.</li>
                )}
              </ul>

              <h3 className="subheading">Assessment item</h3>
              {!gradebook?.grades_released && (
                categories.length > 0 ? (
                  <form className="form-grid" onSubmit={createAssessment}>
                    <label>
                      Category
                      <select name="category_id" required>
                        {categories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name} · {category.weight}%
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Title
                      <input name="title" required maxLength={160} placeholder="Midterm" />
                    </label>
                    <label>
                      Maximum points
                      <input name="max_points" type="number" min="0.01" max="100000" step="0.01" required />
                    </label>
                    <label>
                      Due date
                      <input name="due_date" type="date" />
                    </label>
                    <button className="primary-button" disabled={working}>Add assessment</button>
                  </form>
                ) : (
                  <p className="panel-note">Create a category before adding assessment items.</p>
                )
              )}
            </article>

            <article className="panel roster-panel">
              <div className="panel-title-row">
                <h2>Section roster</h2>
                <span className="term-pill">{roster.length} students</span>
              </div>
              <ul className="record-list">
                {roster.map((student) => (
                  <li key={student.student_id}>
                    <strong>{student.student_name}</strong>
                    <span>{student.student_email}</span>
                  </li>
                ))}
                {roster.length === 0 && <li className="empty-state">No students enrolled.</li>}
              </ul>
            </article>
          </div>

          <section className="panel gradebook-panel">
            <div className="panel-title-row">
              <div>
                <p className="eyebrow">GRADEBOOK</p>
                <h2>Assessment scores</h2>
              </div>
              {!gradebook?.grades_released ? (
                <button className="primary-button" onClick={workflow.releaseGrades} disabled={!canRelease || working}>
                  {working ? "Working..." : "Release final grades"}
                </button>
              ) : (
                <span className="release-badge release-badge--released">
                  Released {gradebook.released_at ? new Date(gradebook.released_at).toLocaleDateString() : ""}
                </span>
              )}
            </div>
            {!canRelease && !gradebook?.grades_released && (
              <p className="panel-note">
                Release becomes available when the category weights total 100% and every active student has a score for every assessment.
              </p>
            )}
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Student</th>
                    {gradebook?.assessments.map((assessment) => (
                      <th scope="col" key={assessment.id}>
                        {assessment.title}
                        <small>{assessment.category_name} · /{assessment.max_points}</small>
                      </th>
                    ))}
                    <th scope="col">Current %</th>
                    <th scope="col">Final</th>
                  </tr>
                </thead>
                <tbody>
                  {gradebook?.students.map((student) => (
                    <tr key={student.student_id}>
                      <th scope="row">
                        {student.student_name}
                        <small>{student.student_email}</small>
                      </th>
                      {gradebook.assessments.map((assessment) => (
                        <td key={assessment.id}>
                          <ScoreCell
                            assessment={assessment}
                            studentId={student.student_id}
                            score={student.scores[String(assessment.id)]}
                            released={gradebook.grades_released}
                            error={fieldErrors[`score:${assessment.id}:${student.student_id}`] ?? ""}
                            onSave={workflow.saveScore}
                          />
                        </td>
                      ))}
                      <td>{student.current_percentage === null ? "—" : `${student.current_percentage}%`}</td>
                      <td>
                        {student.final_percentage === null
                          ? "Incomplete"
                          : `${student.final_percentage}% · ${student.letter_grade}`}
                      </td>
                    </tr>
                  ))}
                  {gradebook?.students.length === 0 && (
                    <tr><td className="empty-cell" colSpan={(gradebook?.assessments.length ?? 0) + 4}>No enrolled students.</td></tr>
                  )}
                  {gradebook?.assessments.length === 0 && gradebook.students.length > 0 && (
                    <tr><td className="empty-cell" colSpan={4}>Add assessment items to start entering scores.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-title-row">
              <div>
                <p className="eyebrow">ACCOUNTABILITY</p>
                <h2>Grade corrections</h2>
              </div>
              <span className="term-pill">{corrections.length} corrections</span>
            </div>
            {corrections.length > 0 ? (
              <div className="table-scroll">
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th scope="col">Student</th>
                      <th scope="col">Assessment</th>
                      <th scope="col">Points</th>
                      <th scope="col">Course grade</th>
                      <th scope="col">Changed by</th>
                      <th scope="col">Reason</th>
                      <th scope="col">When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {corrections.map((correction) => (
                      <tr key={correction.id}>
                        <td>{correction.student_name}</td>
                        <td>{correction.assessment_title}</td>
                        <td>{correction.previous_points} → {correction.new_points}</td>
                        <td>
                          {correction.previous_percentage}% {correction.previous_letter_grade}
                          {" → "}
                          {correction.new_percentage}% {correction.new_letter_grade}
                        </td>
                        <td>{correction.changed_by_name}</td>
                        <td>{correction.reason}</td>
                        <td>{new Date(correction.changed_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">No released-grade corrections recorded for this section.</p>
            )}
          </section>
        </>
      )}
    </section>
  );
}
