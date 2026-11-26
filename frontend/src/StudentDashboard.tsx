import { useEffect, useMemo, useState } from "react";
import {
  apiRequest,
  ReleasedGrade,
  Section,
  WhatIfSimulation,
} from "./api";
import { clampPercentage, gradeTone } from "./gradeDisplay";
import {
  letterForPercentage,
  projectGrade,
  scoreNeededForTarget,
  SimulationScenario,
} from "./gradeSimulator";
import { loadSimulationSections, loadWhatIfSimulation } from "./whatIfData";
import { filterReleasedGrades } from "./studentGradeFilters";

export default function StudentDashboard() {
  const [grades, setGrades] = useState<ReleasedGrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [selectedTerm, setSelectedTerm] = useState("all");
  const [sections, setSections] = useState<Section[]>([]);
  const [simulationSectionId, setSimulationSectionId] = useState("");
  const [simulation, setSimulation] = useState<WhatIfSimulation | null>(null);
  const [scenario, setScenario] = useState<Record<number, string>>({});
  const [targetLetter, setTargetLetter] = useState("");
  const [solveAssessmentId, setSolveAssessmentId] = useState("");
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError, setSimulationError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiRequest<ReleasedGrade[]>("/api/enrollments/mine/grades")
      .then((result) => {
        if (active) setGrades(result);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load released grades.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  useEffect(() => {
    let active = true;
    loadSimulationSections()
      .then((result) => {
        if (active) setSections(result);
      })
      .catch(() => {
        if (active) setSimulationError("Unable to load your enrolled sections.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!simulationSectionId) {
      setSimulation(null);
      return;
    }
    let active = true;
    setSimulationLoading(true);
    setSimulationError("");
    loadWhatIfSimulation(Number(simulationSectionId))
      .then((result) => {
        if (!active) return;
        setSimulation(result);
        const initial: Record<number, string> = {};
        for (const assessment of result.assessments) {
          initial[assessment.id] =
            assessment.points === null ? "" : String(assessment.points);
        }
        setScenario(initial);
        setTargetLetter(result.grade_bands[0]?.code ?? "");
        const last = result.assessments[result.assessments.length - 1];
        setSolveAssessmentId(last ? String(last.id) : "");
      })
      .catch((loadError: unknown) => {
        if (active) {
          setSimulation(null);
          setSimulationError(
            loadError instanceof Error ? loadError.message : "Unable to load the simulator.",
          );
        }
      })
      .finally(() => {
        if (active) setSimulationLoading(false);
      });
    return () => {
      active = false;
    };
  }, [simulationSectionId]);

  const sortedGrades = useMemo(
    () =>
      [...grades].sort(
        (a, b) => Date.parse(b.released_at) - Date.parse(a.released_at),
      ),
    [grades],
  );
  const stats = useMemo(() => {
    const average =
      grades.length > 0
        ? grades.reduce((sum, grade) => sum + grade.percentage, 0) / grades.length
        : 0;
    const best = grades.reduce<ReleasedGrade | null>(
      (top, grade) => (!top || grade.percentage > top.percentage ? grade : top),
      null,
    );
    const termCount = new Set(grades.map((grade) => grade.term_id)).size;
    return [
      { label: "Released grades", value: grades.length, hint: "Published results" },
      { label: "Average", value: `${average.toFixed(1)}%`, hint: "Across released courses" },
      {
        label: "Strongest result",
        value: best ? `${best.percentage}%` : "—",
        hint: best ? `${best.course_code} · ${best.letter_grade}` : "No results yet",
      },
      { label: "Terms", value: termCount, hint: "With released grades" },
    ];
  }, [grades]);
  const terms = useMemo(
    () => Array.from(new Map(grades.map((grade) => [grade.term_id, grade.term_name])).entries()),
    [grades],
  );
  const visibleGrades = useMemo(
    () =>
      filterReleasedGrades(
        sortedGrades,
        search,
        selectedTerm === "all" ? null : Number(selectedTerm),
      ),
    [sortedGrades, search, selectedTerm],
  );
  const simulationScenario = useMemo<SimulationScenario>(() => {
    const values: SimulationScenario = {};
    for (const assessment of simulation?.assessments ?? []) {
      const value = scenario[assessment.id];
      values[assessment.id] = value === undefined || value.trim() === "" ? null : Number(value);
    }
    return values;
  }, [simulation, scenario]);
  const projection = useMemo(
    () =>
      simulation
        ? projectGrade(simulation.categories, simulation.assessments, simulationScenario)
        : null,
    [simulation, simulationScenario],
  );
  const targetBand = simulation?.grade_bands.find((band) => band.code === targetLetter);
  const solvedAssessment = simulation?.assessments.find(
    (assessment) => String(assessment.id) === solveAssessmentId,
  );
  const targetScore = useMemo(
    () =>
      simulation && targetBand && solvedAssessment
        ? scoreNeededForTarget(
            simulation.categories,
            simulation.assessments,
            solvedAssessment.id,
            targetBand.minimum_percentage,
            simulationScenario,
          )
        : null,
    [simulation, targetBand, solvedAssessment, simulationScenario],
  );

  return (
    <section
      className="dashboard-layout"
      aria-labelledby="student-title"
      aria-busy={loading}
    >
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">STUDENT WORKSPACE</p>
          <h1 id="student-title">My course grades</h1>
          <p className="welcome-copy">
            Only grades released by your instructors appear here.
          </p>
        </div>
        <span className="term-pill">
          {grades.length} released {grades.length === 1 ? "grade" : "grades"}
        </span>
      </div>

      {!loading && !error && grades.length > 0 && (
        <div className="stat-grid">
          {stats.map((stat, index) => (
            <article
              className={`stat-card ${index === 0 ? "stat-card--accent" : ""}`}
              key={stat.label}
            >
              <span className="stat-label">{stat.label}</span>
              <strong className="stat-value">{stat.value}</strong>
              <span className="stat-hint">{stat.hint}</span>
            </article>
          ))}
        </div>
      )}

      {!loading && !error && grades.length > 0 && (
        <div className="student-grade-filters">
          <label>
            Search grades
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Course, section, or term"
            />
          </label>
          <label>
            Filter by term
            <select
              value={selectedTerm}
              onChange={(event) => setSelectedTerm(event.target.value)}
            >
              <option value="all">All terms</option>
              {terms.map(([termId, termName]) => (
                <option key={termId} value={termId}>
                  {termName}
                </option>
              ))}
            </select>
          </label>
          <p className="panel-note filter-status" role="status" aria-live="polite">
            Showing {visibleGrades.length} of {grades.length} released{" "}
            {grades.length === 1 ? "grade" : "grades"}
          </p>
        </div>
      )}

      {error ? (
        <div className="dashboard-message">
          <p className="form-error" role="alert">{error}</p>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
          >
            Try again
          </button>
        </div>
      ) : loading ? (
        <>
          <div className="student-grade-grid" aria-hidden="true">
            <span className="skeleton skeleton-grade-card" />
            <span className="skeleton skeleton-grade-card" />
            <span className="skeleton skeleton-grade-card" />
          </div>
          <p className="visually-hidden" role="status" aria-live="polite">
            Loading your grades...
          </p>
        </>
      ) : grades.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No released grades yet</h2>
          <p>Your released course results will appear here.</p>
        </section>
      ) : visibleGrades.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No matching grades</h2>
          <p>Try a different search or term filter.</p>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              setSearch("");
              setSelectedTerm("all");
            }}
          >
            Clear filters
          </button>
        </section>
      ) : (
        <div className="student-grade-grid">
          {visibleGrades.map((grade) => {
            const tone = gradeTone(grade.letter_grade);
            return (
              <article className="student-grade-card" key={grade.section_id}>
                <div>
                  <p className="eyebrow">{grade.term_name}</p>
                  <h2>{grade.course_code}</h2>
                  <p className="student-course-title">{grade.course_title}</p>
                  <span className="section-caption">Section {grade.section_code}</span>
                </div>
                <div
                  className={`grade-result grade-result--${tone}`}
                  role="group"
                  aria-label={`Final grade ${grade.letter_grade}, ${grade.percentage} percent`}
                >
                  <strong>{grade.letter_grade}</strong>
                  <span>{grade.percentage}%</span>
                </div>
                <div
                  className={`grade-meter grade-meter--${tone}`}
                  aria-hidden="true"
                >
                  <span style={{ width: `${clampPercentage(grade.percentage)}%` }} />
                </div>
                <p className="released-caption">
                  Released {new Date(grade.released_at).toLocaleDateString()}
                </p>
              </article>
            );
          })}
        </div>
      )}

      <section className="panel what-if-panel" aria-labelledby="what-if-title">
        <div className="panel-heading-row">
          <div>
            <p className="eyebrow">PRIVATE PLANNING</p>
            <h2 id="what-if-title">What-if grade simulator</h2>
            <p className="panel-note">
              Try hypothetical scores and see what you need on one assessment to reach a
              target grade. Nothing you enter here changes a recorded score.
            </p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            Enrolled section
            <select
              value={simulationSectionId}
              onChange={(event) => setSimulationSectionId(event.target.value)}
            >
              <option value="">Choose a section</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.course_code} · {section.section_code} · {section.term_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Target grade
            <select
              value={targetLetter}
              disabled={!simulation}
              onChange={(event) => setTargetLetter(event.target.value)}
            >
              {simulation?.grade_bands.map((band) => (
                <option key={band.code} value={band.code}>
                  {band.code} ({band.minimum_percentage}%)
                </option>
              ))}
            </select>
          </label>
        </div>
        {simulationError && (
          <p className="form-error" role="alert">{simulationError}</p>
        )}
        {simulationLoading && (
          <p className="panel-note" role="status" aria-live="polite">
            Loading simulator data...
          </p>
        )}
        {simulation && projection && (
          <>
            <div className="simulator-summary">
              <article>
                <span className="stat-label">Hypothetical course grade</span>
                <strong>{letterForPercentage(simulation.grade_bands, projection.projected_percentage)}</strong>
                <span className="stat-hint">
                  {projection.projected_percentage === null
                    ? "Add a score for every assessment to project a final grade"
                    : `${projection.projected_percentage}% projected`}
                </span>
              </article>
              <article>
                <span className="stat-label">Average over graded categories</span>
                <strong>
                  {projection.current_percentage === null
                    ? "—"
                    : `${projection.current_percentage}%`}
                </strong>
                <span className="stat-hint">
                  {projection.graded_weight}% of category weights have scores
                </span>
              </article>
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <caption>Assessment scores and hypothetical values</caption>
                <thead>
                  <tr>
                    <th scope="col">Assessment</th>
                    <th scope="col">Category</th>
                    <th scope="col">Maximum</th>
                    <th scope="col">Recorded</th>
                    <th scope="col">Hypothetical score</th>
                    <th scope="col">Solve for</th>
                  </tr>
                </thead>
                <tbody>
                  {simulation.assessments.map((assessment) => {
                    const category = simulation.categories.find(
                      (item) => item.id === assessment.category_id,
                    );
                    return (
                      <tr key={assessment.id}>
                        <th scope="row">
                          {assessment.title}
                          {assessment.due_date && (
                            <small>Due {new Date(assessment.due_date).toLocaleDateString()}</small>
                          )}
                        </th>
                        <td>
                          {category?.name ?? "—"}
                          {category && <small>{category.weight}% of grade</small>}
                        </td>
                        <td>{assessment.max_points}</td>
                        <td>
                          {simulation.grades_released && assessment.points !== null
                            ? `${assessment.points} pts`
                            : "Not visible"}
                        </td>
                        <td>
                          <label className="visually-hidden" htmlFor={`what-if-${assessment.id}`}>
                            Hypothetical score for {assessment.title}
                          </label>
                          <input
                            id={`what-if-${assessment.id}`}
                            type="number"
                            min="0"
                            max={assessment.max_points}
                            step="0.01"
                            placeholder="—"
                            value={scenario[assessment.id] ?? ""}
                            onChange={(event) =>
                              setScenario((current) => ({
                                ...current,
                                [assessment.id]: event.target.value,
                              }))
                            }
                          />
                        </td>
                        <td>
                          <input
                            type="radio"
                            name="solve-assessment"
                            value={assessment.id}
                            checked={String(assessment.id) === solveAssessmentId}
                            onChange={() => setSolveAssessmentId(String(assessment.id))}
                            aria-label={`Solve target grade using ${assessment.title}`}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {targetScore && solvedAssessment && (
              <div
                className={`simulator-target ${targetScore.attainable ? "" : "simulator-target--warning"}`}
                role="status"
                aria-live="polite"
              >
                {targetScore.reason === "ok" ? (
                  <p>
                    To reach <strong>{targetLetter}</strong>, score at least{" "}
                    <strong>{targetScore.required_points} points</strong> (
                    {targetScore.required_percentage}%) on {solvedAssessment.title}.
                  </p>
                ) : targetScore.reason === "unreachable" ? (
                  <p>
                    {targetLetter} is not reachable through {solvedAssessment.title} alone.
                    The highest attainable course grade with this scenario is{" "}
                    <strong>{targetScore.maximum_percentage}%</strong>.
                  </p>
                ) : (
                  <p>
                    Category weights in this section do not total 100%, so a final grade
                    target cannot be calculated.
                  </p>
                )}
              </div>
            )}
          </>
        )}
        {!simulation && !simulationLoading && !simulationError && (
          <p className="empty-state">
            Choose an enrolled section to explore your assessment scores and targets.
          </p>
        )}
      </section>
    </section>
  );
}
