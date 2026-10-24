# OSTutorLLM requirements comparison

Reviewed on 24 October 2026 against the user's pasted project brief, the current
source, README, tests, and the three local Word project reports.

No separately named question paper or marking rubric was found in the project
folder. The pasted text is treated as the reference brief. It contains model
recommendations, alternative architectures and possible research contributions;
these cannot all be treated as compulsory assessment criteria without a rubric.

## Current capability and gaps

| Brief item | Status | Evidence and remaining work |
| --- | --- | --- |
| Web interface for OS learning | Implemented | Responsive HTML interface, topic selection, four answer styles and quizzes. No separate native mobile app. |
| Instruction-following LLM for teaching | Implemented for topic notes | Groq generates expanded lesson explanations, revision points and simpler explanations. General Ask OSTutor answers still use lexical retrieval and templates. |
| RAG over institutional teaching material | Missing | No course-file upload, PDF/PPT extraction, section chunking, embedding model or vector index. Groq receives the bundled topic outline; this is limited prompt grounding rather than the proposed document RAG pipeline. |
| Exact supporting citations | Partial | Broad labels such as OS Faculty Notes are shown, but there are no verified document/page references or links to retrieved passages. |
| Personalized feedback based on performance | Partial | Two-question checks gate advancement; mistakes reveal an easier explanation. The simpler explanation is prepared for the part, rather than generated from a particular student's mistakes. |
| Adaptive difficulty for theory and practical work | Partial | Review versus progression is supported. There is no difficulty ladder, learner mastery model or adaptive practical exercise selection. |
| Automatic MCQ and viva generation | Missing | Existing general quiz and lesson checks are authored in code. Viva mode adds answer guidance, not generated viva question sets. |
| Automatic shell labs and lab solutions | Missing | Practical Lab mode adds a template suffix. There is no lab generator, code assessment or execution environment. |
| Numerical OS problem solving | Partial introductory coverage | Concepts and fixed examples exist. There are no scheduling/Gantt solvers, page-fault simulators, disk scheduling solvers or full Banker safety/request exercises. |
| Domain-specific educational fine-tuning | Missing; optional architecture choice | No institution-specific training dataset, training pipeline or adapted model. Calling an instruction-tuned model does not constitute custom fine-tuning. |
| Institutional knowledge collection | Missing | Only 19 short curated knowledge records are bundled. Course textbooks, faculty notes, lab manuals, PPTs, previous papers and other listed materials are not ingested. The brief's source list supplies possible corpus inputs, not proof that every listed format is mandatory. |
| Local/offline institutional hosting | Missing; optional deployment choice | Notes use cloud Groq; built-in notes remain available without it. There is no local model inference service. |
| Research evaluation | Partial | Functional tests, one live Groq topic test and a small retrieval diagnostic exist. There is no instructor-reviewed answer benchmark, citation evaluation, baseline comparison of RAG/fine-tuning or measured student learning study. |
| Long-term learner progress | Missing supporting capability | Sessions survive refresh in the same tab but expire and reset on server restart. No persistent learner profiles or longitudinal performance records. This supports personalization but is not explicitly specified as a separate requirement in the pasted brief. |

## Topic coverage compared with the brief

Covered at an introductory level: CPU scheduling (Round Robin, FCFS, SJF and
priority), deadlock concepts, memory management, paging and segmentation, file
systems, threads, and synchronization through critical sections, semaphores and
mutexes.

Missing dedicated lessons:

- Linux commands.
- Shell programming and Bash scripting.
- Disk scheduling.
- Producer-consumer problem.
- Dining philosophers.

Partial topics needing deeper material:

- Linux system calls: fork is covered, but there is no broader system-call unit
  covering examples such as exec, wait, pipes and file I/O.
- Banker's algorithm: introduced under prevention/avoidance, without a full
  worked allocation/need/available matrix or safe-sequence exercise.
- Numerical scheduling and replacement: definitions and examples exist, but
  there are no general worked-problem tools.

The brief's model-to-topic recommendations do not require implementing a model
router, using every named provider, or selecting a different model per topic.

## Reports needing revision

All three local Word reports describe the earlier lexical-retrieval prototype.
They omit Groq generation, the guided lesson flow, current tests and the white
and green interface. The later reports also reproduce the old quiz-order defect
as an unresolved problem; the current frontend submits IDs and grading honors
that order. Older exported PDF/report artifacts should be regenerated from an
updated report before submission.

The title “A Retrieval-Augmented and Fine-Tuned Large Language Model for
Personalized Operating Systems Education” describes the proposed research
scope. The current implementation should not claim document RAG or custom
fine-tuning. If that exact title is required, both components remain work to do.
Otherwise choose an honest title describing the implemented adaptive OS tutor.

## Suggested implementation order

1. Build course-document ingestion and document RAG, with precise citations,
   and connect it to general questions as well as lessons.
2. Add missing syllabus topics and reviewed numerical exercises.
3. Generate and validate MCQs, viva questions and shell labs from the retrieved
   course content.
4. Record progress persistently and make revision target the learner's mistakes.
5. Evaluate retrieval, factual correctness, citations and student learning with
   instructor review; update the submission reports with measured evidence.
6. Add custom fine-tuning if required by the selected research scope. It is an
   alternative/extension in the pasted brief rather than a prerequisite for
   implementing its recommended RAG route.

## Source evidence

- `app.py`: knowledge records, lexical ask endpoint, authored quizzes, in-memory
  lesson state and grading.
- `lessons.py`: 19 topics and two curated parts per topic.
- `groq_notes.py`: hosted generation from bundled outlines and fallback.
- `static/lessons.js`: lesson/review/progression interface and tab-session resume.
- `README.md` and `TEST_REPORT.md`: current scope and testing boundaries.
- `OSTutorLLM_Project_Report_Improved.docx`,
  `OSTutorLLM_Report_Final.docx`, `OSTutorLLM_Report_5_Pages.docx`: earlier
  report contents, dataset descriptions and proposed extensions.
