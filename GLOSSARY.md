# Student Grade Management

A system for managing course offerings, student assessment results, and released course grades at a single institution.

## People

**Student**:
A person enrolled in a course section who can view their released grades.

**Instructor**:
A person assigned to teach a course section and manage its assessment results.

**Academic administrator**:
A person who manages academic periods, courses, sections, and student enrollment.

## Academic structure

**Academic year**:
An institution-defined span of time that groups academic terms.

**Term**:
A dated academic period within an academic year in which courses are offered.
_Avoid_: Semester, unless the institution specifically uses that term

**Course**:
A subject of study that may be offered to students in one or more terms.

**Section**:
A specific offering of a course in a term, with its own instructor and enrolled students.
_Avoid_: Class, when referring to the course itself

**Enrollment**:
A student's membership in a particular course section.

## Grades

**Assessment**:
A piece of work, such as an assignment or exam, for which a student receives a score.

**Assessment score**:
The points earned by one student on one assessment.

**Course grade**:
A student's calculated result for one course section, represented as a percentage and a letter grade.

**Instructor gradebook**:
An instructor's working record for a section, containing its assessments, student assessment scores, and current course grade calculations.

**Grade release**:
The instructor's action that makes course grades visible to enrolled students.

**Grade correction**:
A change to a previously released grade that retains the prior value and correction history.

**What-if simulation**:
A private, read-only calculation that shows how hypothetical assessment scores would change a student's course grade. A simulation never writes an assessment score.

**Grade change request**:
A proposed correction to a released grade. An instructor submits a request; an academic administrator reviews it before the score changes. A request records a reason code, an explanation, the requester, and the submission time.

**Reason code**:
A controlled category describing why a grade change was requested, such as a grading error, misgraded work, a data-entry mistake, or a retake.

**Grade change approval**:
An academic administrator's decision to apply or reject a grade change request, recorded with the reviewer and decision time.

**Audit event**:
An immutable record of a grade change transition (request, approval, or rejection) with its actor and timestamp. Audit events are append-only and are kept separately from the current state of a request.
