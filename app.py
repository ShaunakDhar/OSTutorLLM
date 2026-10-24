"""
OSTutorLLM — Operating Systems Virtual Professor
Improved educational prototype: weighted lexical retrieval, confidence-aware fallback,
source attribution, quiz endpoints, health/statistics endpoints, and request validation.

Topic lessons can use Groq-generated notes grounded in the curated outline.
Question answering uses lexical retrieval; embeddings and vector search are future work.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from time import perf_counter
import re
import random
from typing import Literal
from threading import RLock
from time import monotonic
from uuid import uuid4
from lessons import LESSONS
from groq_notes import topic_notes, notes_configuration

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="OSTutorLLM — Operating Systems Virtual Professor",
    description="A source-aware OS study assistant prototype.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# A small, hand-curated dataset for the demonstration. Expand only with permitted materials.
KNOWLEDGE = [
    {"id":"OS-01","topic":"Round Robin Scheduling","category":"CPU Scheduling",
     "keywords":["round robin","time quantum","preemptive","rr"],
     "source":"OS Faculty Notes / CPU Scheduling",
     "content":"Round Robin is a preemptive CPU scheduling algorithm. Each ready process receives a fixed time quantum in circular FIFO order. If it does not finish in that quantum, it returns to the ready queue. A smaller quantum improves responsiveness but increases context-switch overhead; a very large quantum makes Round Robin behave more like FCFS."},
    {"id":"OS-02","topic":"FCFS Scheduling","category":"CPU Scheduling",
     "keywords":["fcfs","first come first served","arrival order","convoy effect"],
     "source":"OS Faculty Notes / CPU Scheduling",
     "content":"First Come First Served (FCFS) executes processes in arrival order. It is simple and non-preemptive. A long process at the front can delay shorter processes, a limitation commonly described as the convoy effect."},
    {"id":"OS-03","topic":"Shortest Job First","category":"CPU Scheduling",
     "keywords":["sjf","shortest job","burst time","starvation"],
     "source":"OS Faculty Notes / CPU Scheduling",
     "content":"Shortest Job First (SJF) selects the available process with the smallest CPU burst. When burst lengths are known, it can minimize average waiting time. Long jobs may starve if shorter jobs keep arriving. The preemptive variant is commonly called Shortest Remaining Time First."},
    {"id":"OS-04","topic":"Priority Scheduling","category":"CPU Scheduling",
     "keywords":["priority","aging","starvation"],
     "source":"OS Faculty Notes / CPU Scheduling",
     "content":"Priority scheduling chooses a process according to its priority value and may be preemptive or non-preemptive. The exact meaning of a high numeric value depends on the convention used. Aging gradually improves the priority of waiting processes to reduce starvation."},
    {"id":"OS-05","topic":"Paging","category":"Memory Management",
     "keywords":["paging","page","frame","external fragmentation"],
     "source":"OS Textbook / Memory Management",
     "content":"Paging divides logical memory into fixed-size pages and physical memory into equal-size frames. A page table maps pages to frames. Paging avoids external fragmentation, although the final page may have internal fragmentation and page-table storage adds overhead."},
    {"id":"OS-06","topic":"Segmentation","category":"Memory Management",
     "keywords":["segmentation","segment","logical units","external fragmentation"],
     "source":"OS Textbook / Memory Management",
     "content":"Segmentation divides a program into variable-sized logical units such as code, data and stack. A logical address is represented by a segment number and offset. Segmentation reflects program structure but can suffer external fragmentation."},
    {"id":"OS-07","topic":"Virtual Memory","category":"Memory Management",
     "keywords":["virtual memory","demand paging","page fault","thrashing"],
     "source":"OS Faculty Notes / Virtual Memory",
     "content":"Virtual memory lets a process use a logical address space that may be larger than available physical RAM. Demand paging loads pages when needed. A page fault occurs when a referenced page is not currently resident. Excessive page faults can lead to thrashing."},
    {"id":"OS-08","topic":"Page Replacement","category":"Memory Management",
     "keywords":["page replacement","fifo","lru","optimal","reference string"],
     "source":"OS Textbook / Memory Management",
     "content":"Page replacement chooses a resident page to remove when a needed page must be loaded and no free frame is available. FIFO removes the page loaded earliest; LRU removes the least recently used page; Optimal replaces the page whose next use is farthest in the future and is mainly a theoretical benchmark."},
    {"id":"OS-09","topic":"First Fit Memory Allocation","category":"Memory Management",
     "keywords":["first fit","memory allocation","partition","hole"],
     "source":"OS Faculty Notes / Memory Management",
     "content":"First Fit scans free memory blocks from the beginning and allocates a process to the first block large enough. It is simple and often fast, but repeated allocations can leave scattered free holes."},
    {"id":"OS-10","topic":"Process States","category":"Process Management",
     "keywords":["process state","new","ready","running","waiting","terminated"],
     "source":"OS Faculty Notes / Process Management",
     "content":"Common process states are New, Ready, Running, Waiting/Blocked and Terminated. The scheduler dispatches a ready process to run. An I/O request may move a running process to Waiting; completion can return it to Ready."},
    {"id":"OS-11","topic":"Process vs Thread","category":"Process Management",
     "keywords":["process vs thread","thread","multithreading","address space"],
     "source":"OS Faculty Notes / Process Management",
     "content":"A process is an executing program with its own address space and resources. Threads are execution units within a process and typically share code and data, while each thread has its own stack and processor state. Threads can communicate efficiently but require synchronization for shared data."},
    {"id":"OS-12","topic":"Context Switching","category":"Process Management",
     "keywords":["context switch","context switching","registers","overhead"],
     "source":"OS Faculty Notes / Process Management",
     "content":"A context switch saves the CPU state of the current process or thread and restores the state of another. It enables multitasking but creates overhead because the CPU spends time switching rather than executing application instructions."},
    {"id":"OS-13","topic":"Process Creation with fork","category":"Process Management",
     "keywords":["fork","process creation","parent","child","pid"],
     "source":"POSIX Lab Manual / Process Control",
     "content":"On Unix-like systems, fork() creates a child process. After a successful call, both parent and child continue execution. fork() returns the child process ID to the parent and zero to the child; failure is indicated by a negative return value."},
    {"id":"OS-14","topic":"Deadlock Conditions","category":"Deadlocks",
     "keywords":["deadlock","mutual exclusion","hold and wait","no preemption","circular wait"],
     "source":"OS Faculty Notes / Deadlocks",
     "content":"Deadlock is a situation in which a set of processes waits indefinitely for resources held by one another. The four necessary conditions are mutual exclusion, hold and wait, no preemption, and circular wait. All four must hold simultaneously for a deadlock to occur."},
    {"id":"OS-15","topic":"Deadlock Prevention and Avoidance","category":"Deadlocks",
     "keywords":["deadlock prevention","deadlock avoidance","banker's algorithm","safe state","banker"],
     "source":"OS Faculty Notes / Deadlock Avoidance",
     "content":"Deadlock prevention breaks at least one necessary deadlock condition. Deadlock avoidance checks whether granting a request leaves the system in a safe state. Banker's algorithm uses Available, Max, Allocation and Need information to test for a safe sequence."},
    {"id":"OS-16","topic":"Critical Section","category":"Synchronization",
     "keywords":["critical section","race condition","mutual exclusion","bounded waiting"],
     "source":"POSIX Lab Manual / Threads",
     "content":"A critical section accesses shared data or resources. A correct solution aims for mutual exclusion, progress and bounded waiting. Without suitable synchronization, interleaved operations can cause race conditions and inconsistent results."},
    {"id":"OS-17","topic":"Semaphore and Mutex","category":"Synchronization",
     "keywords":["semaphore","mutex","lock","wait","signal"],
     "source":"POSIX Lab Manual / Threads",
     "content":"A semaphore is a synchronization primitive commonly controlled through wait and signal operations. A mutex is used to provide exclusive access to a protected resource. A typical mutex pattern is lock, execute the critical section, then unlock."},
    {"id":"OS-18","topic":"File Allocation Methods","category":"File Systems",
     "keywords":["file allocation","contiguous allocation","linked allocation","indexed allocation"],
     "source":"OS Textbook / File Systems",
     "content":"Contiguous allocation stores a file in consecutive disk blocks and supports fast sequential access but can suffer external fragmentation. Linked allocation connects blocks with pointers but is less convenient for random access. Indexed allocation stores block pointers in an index structure."},
    {"id":"OS-19","topic":"File System Basics","category":"File Systems",
     "keywords":["file system","directory","inode","metadata","permissions"],
     "source":"OS Textbook / File Systems",
     "content":"A file system organizes files and directories on storage. It manages names, metadata, permissions and allocation of disk space. In Unix-like file systems, an inode stores metadata and block references, while directory entries associate names with inode numbers."},
]

QUIZ = [
 {"id":"Q1","q":"Which scheduling algorithm uses a fixed time quantum?","options":["FCFS","Round Robin","SJF","Priority"],"answer":1,"explain":"Round Robin gives each ready process a fixed time slice."},
 {"id":"Q2","q":"Which technique divides memory into fixed-size pages and frames?","options":["Segmentation","Paging","Compaction","Spooling"],"answer":1,"explain":"Paging uses fixed-size pages in logical memory and frames in physical memory."},
 {"id":"Q3","q":"Which is NOT one of the four necessary deadlock conditions?","options":["Circular wait","No preemption","Hold and wait","Context switching"],"answer":3,"explain":"The four are mutual exclusion, hold and wait, no preemption and circular wait."},
 {"id":"Q4","q":"What does fork() return to the child after a successful call?","options":["The parent PID","Zero","-1","The number of threads"],"answer":1,"explain":"fork() returns zero in the child and the child PID in the parent."},
 {"id":"Q5","q":"Which page replacement algorithm removes the least recently used page?","options":["FIFO","LRU","Optimal","FCFS"],"answer":1,"explain":"LRU replaces the page that has not been used for the longest time in the past."},
 {"id":"Q6","q":"What is the primary purpose of a mutex?","options":["Exclusive access","Page replacement","Disk formatting","CPU burst prediction"],"answer":0,"explain":"A mutex protects a critical section by allowing one thread at a time."},
 {"id":"Q7","q":"Which allocation method uses an index block or index structure?","options":["Contiguous","Linked","Indexed","Round Robin"],"answer":2,"explain":"Indexed allocation stores pointers to a file's blocks in an index structure."},
 {"id":"Q8","q":"Which technique can help reduce starvation in priority scheduling?","options":["Aging","Thrashing","Paging","Spooling"],"answer":0,"explain":"Aging gradually raises the priority of processes that wait for a long time."},
]

MODES = {"Beginner", "Exam Revision", "Viva & Interview", "Practical Lab"}
stats = Counter()
latencies_ms: list[float] = []

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    mode: Literal["Beginner", "Exam Revision", "Viva & Interview", "Practical Lab"] = "Exam Revision"
    category: str = "All Topics"

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank.")
        return value

class QuizSubmission(BaseModel):
    answers: list[int] = Field(min_length=1, max_length=len(QUIZ))
    question_ids: list[str] | None = None


# Guided progress is isolated per session and expires after a day of inactivity.
lesson_sessions: dict[str, dict] = {}
lesson_lock = RLock()


class LessonStart(BaseModel):
    topic_id: str


class LessonAnswers(BaseModel):
    part_index: int = Field(ge=0, strict=True)
    attempt: int = Field(ge=0, strict=True)
    answers: dict[str, int] = Field(min_length=2, max_length=2)

    @field_validator('answers', mode='before')
    @classmethod
    def valid_choices(cls, value):
        if not isinstance(value, dict) or any(type(v) is not int or v not in (0, 1) for v in value.values()):
            raise ValueError('Choose one of the two options for each question.')
        return value


def lesson_session(session_id):
    session = lesson_sessions.get(session_id)
    if not session or monotonic() - session['touched'] > 86400:
        lesson_sessions.pop(session_id, None)
        raise HTTPException(404, 'Lesson expired. Choose a topic to start again.')
    session['touched'] = monotonic()
    return session


def prepare_check(session):
    lesson = session['parts'][session['part_index']]
    questions = []
    for i, (prompt, correct, distractor) in enumerate(lesson['questions']):
        options = random.sample([correct, distractor], 2)
        questions.append(dict(id=str(i), q=prompt, options=options, answer=options.index(correct)))
    session['questions'] = random.sample(questions, len(questions))


def lesson_view(session_id, session):
    topic = next(t for t in KNOWLEDGE if t['id'] == session['topic_id'])
    parts = session['parts']
    lesson = parts[session['part_index']]
    return dict(session_id=session_id, topic_id=topic['id'], topic=topic['topic'],
                source=topic['source'], notes_provider=session['notes_provider'],
                notes_model=session['notes_model'], notes_notice=session['notes_notice'],
                key_points=lesson.get('key_points', []),
                part_index=session['part_index'], total_parts=len(parts),
                completed_parts=session['part_index'] + int(session['phase'] in ('passed', 'complete')),
                title=lesson['title'], explanation=lesson['explanation'], example=lesson['example'],
                simpler=lesson['simpler'] if session['phase'] == 'review' else None,
                phase=session['phase'], attempt=session['attempt'], required_correct=2,
                questions=[{k:q[k] for k in ('id', 'q', 'options')} for q in session['questions']])


@app.post('/api/lessons/start')
def start_lesson(body: LessonStart):
    if body.topic_id not in LESSONS:
        raise HTTPException(404, 'Topic not found.')
    topic = next(t for t in KNOWLEDGE if t['id'] == body.topic_id)
    # Network I/O must not hold the global progress lock: other students can
    # continue studying while one topic's notes are generated.
    notes = topic_notes(topic, LESSONS[body.topic_id])
    with lesson_lock:
        for key in list(lesson_sessions):
            if monotonic() - lesson_sessions[key]['touched'] > 86400:
                del lesson_sessions[key]
        if len(lesson_sessions) >= 1000:
            raise HTTPException(503, 'Too many active lessons. Please try again later.')
        session_id = str(uuid4())
        session = dict(topic_id=body.topic_id, part_index=0, phase='learn', attempt=0, touched=monotonic(),
                       parts=notes['parts'], notes_provider=notes['provider'],
                       notes_model=notes['model'], notes_notice=notes['notice'])
        prepare_check(session)
        lesson_sessions[session_id] = session
        return lesson_view(session_id, session)


@app.get('/api/lessons/{session_id}')
def get_lesson(session_id: str):
    with lesson_lock:
        return lesson_view(session_id, lesson_session(session_id))


@app.post('/api/lessons/{session_id}/check')
def check_lesson(session_id: str, body: LessonAnswers):
    with lesson_lock:
        session = lesson_session(session_id)
        if session['phase'] not in ('learn', 'review') or body.part_index != session['part_index'] or body.attempt != session['attempt']:
            raise HTTPException(409, 'This check has already changed. Resume the lesson and try again.')
        if set(body.answers) != {q['id'] for q in session['questions']}:
            raise HTTPException(422, 'Answer both questions in this part.')
        results = [dict(question=q['q'], correct=body.answers[q['id']] == q['answer'],
                        selected_answer=q['options'][body.answers[q['id']]],
                        correct_answer=q['options'][q['answer']]) for q in session['questions']]
        score = sum(r['correct'] for r in results)
        passed = score == 2
        session['phase'] = ('complete' if session['part_index'] == len(session['parts'])-1 else 'passed') if passed else 'review'
        session['attempt'] += 1
        if not passed:
            prepare_check(session)
        stats['lesson_checks'] += 1
        return dict(score=score, total=2, passed=passed, results=results, lesson=lesson_view(session_id, session))


@app.post('/api/lessons/{session_id}/next')
def next_lesson(session_id: str):
    with lesson_lock:
        session = lesson_session(session_id)
        if session['phase'] != 'passed':
            raise HTTPException(409, 'Pass the current check before moving on.')
        session['part_index'] += 1
        session['phase'] = 'learn'
        session['attempt'] = 0
        prepare_check(session)
        return lesson_view(session_id, session)

def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))

def retrieve(question: str, category: str = "All Topics", limit: int = 3) -> list[dict]:
    """Weighted lexical retrieval; transparent and dependency-light, not semantic embeddings."""
    qtokens = tokenize(question)
    if not qtokens:
        return []
    scored = []
    for item in KNOWLEDGE:
        if category != "All Topics" and item["category"] != category:
            continue
        title_tokens = tokenize(item["topic"])
        keyword_tokens = set().union(*(tokenize(k) for k in item["keywords"]))
        body_tokens = tokenize(item["content"])
        score = 4 * len(qtokens & title_tokens) + 3 * len(qtokens & keyword_tokens) + len(qtokens & body_tokens)
        # Phrase bonus rewards direct concept mentions.
        qnorm = " ".join(question.lower().split())
        for phrase in [item["topic"].lower(), *item["keywords"]]:
            if len(phrase) >= 4 and phrase in qnorm:
                score += 5
        # Normalize by query size to reduce bias toward long questions.
        normalized = score / max(1, len(qtokens) ** 0.5)
        if score > 0:
            scored.append((normalized, score, item))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [{"id":d["id"],"topic":d["topic"],"category":d["category"],"source":d["source"],
             "content":d["content"],"score":round(norm,3)} for norm,_,d in scored[:limit]]

def format_answer(question: str, mode: str, docs: list[dict]) -> str:
    content = docs[0]["content"]
    q = question.lower()
    if mode == "Beginner":
        prefix = "Simple explanation: "
        suffix = "\n\nRemember: focus on the main idea first, then learn the technical terms."
    elif mode == "Viva & Interview":
        prefix = "Viva answer: "
        suffix = "\n\nFollow-up to prepare: define the key term and give one advantage or limitation."
    elif mode == "Practical Lab":
        prefix = "Lab focus: "
        suffix = "\n\nIn a lab record, include the objective, input/assumptions, steps, output and observation."
    else:
        prefix = "Exam-ready answer: "
        suffix = "\n\nFor a long-answer question, add a definition, working, advantages/limitations and a small example or diagram."
    if len(docs) > 1 and docs[1]["score"] >= docs[0]["score"] * 0.72:
        content += "\n\nRelated concept: " + docs[1]["content"]
    return prefix + content + suffix

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"status":"ok","app":"OSTutorLLM","version":app.version,"knowledge_entries":len(KNOWLEDGE),
            "topic_notes":notes_configuration()}

@app.get("/api/topics")
def topics():
    categories = sorted({item["category"] for item in KNOWLEDGE})
    return {"categories":categories,"topics":[{"id":d["id"],"topic":d["topic"],"category":d["category"],"source":d["source"]} for d in KNOWLEDGE]}

@app.post("/api/ask")
def ask(body: AskRequest):
    started = perf_counter()
    docs = retrieve(body.question, body.category)
    if not docs or docs[0]["score"] < 0.35:
        stats["low_confidence"] += 1
        stats["questions"] += 1
        return {"answer":"I could not find a confident match in the current OS knowledge base. Try a more specific question about scheduling, paging, virtual memory, deadlocks, processes, synchronization or file systems.",
                "sources":[],"confidence":"low","mode":body.mode,"latency_ms":round((perf_counter()-started)*1000,2)}
    answer_text = format_answer(body.question, body.mode, docs)
    elapsed = round((perf_counter()-started)*1000, 2)
    stats["questions"] += 1
    stats["matched_questions"] += 1
    stats["mode_"+body.mode] += 1
    latencies_ms.append(elapsed)
    del latencies_ms[:-500]
    return {"answer":answer_text,"sources":[{k:d[k] for k in ("id","topic","category","source","score")} for d in docs],
            "confidence":"medium" if docs[0]["score"] < 2 else "high","mode":body.mode,"latency_ms":elapsed}

@app.get("/api/quiz")
def get_quiz():
    questions = random.sample(QUIZ, len(QUIZ))
    return {"questions":[{"id":q["id"],"q":q["q"],"options":q["options"]} for q in questions]}

@app.post("/api/quiz/submit")
def submit_quiz(body: QuizSubmission):
    if len(body.answers) != len(QUIZ):
        raise HTTPException(status_code=422, detail=f"Submit exactly {len(QUIZ)} answers.")
    ordered_questions = QUIZ
    if body.question_ids is not None:
        lookup = {q['id']:q for q in QUIZ}
        if len(body.question_ids) != len(QUIZ) or set(body.question_ids) != set(lookup):
            raise HTTPException(422, 'Submit each quiz question ID exactly once.')
        ordered_questions = [lookup[qid] for qid in body.question_ids]
    results, score = [], 0
    for question, selected in zip(ordered_questions, body.answers):
        valid = 0 <= selected < len(question["options"])
        correct = valid and selected == question["answer"]
        score += int(correct)
        results.append({"id":question["id"],"question":question["q"],"correct":correct,
                        "selected_answer":question["options"][selected] if valid else "Not answered",
                        "correct_answer":question["options"][question["answer"]],"explanation":question["explain"]})
    stats["quizzes"] += 1
    stats["quiz_correct"] += score
    return {"score":score,"total":len(QUIZ),"percentage":round(score/len(QUIZ)*100),"results":results}

@app.get("/api/metrics")
def metrics():
    return {"questions":stats["questions"],"matched_questions":stats["matched_questions"],
            "low_confidence":stats["low_confidence"],"quizzes_submitted":stats["quizzes"],
            "average_latency_ms":round(sum(latencies_ms)/len(latencies_ms),2) if latencies_ms else None,
            "note":"Prototype runtime counters only; restart clears them. These are not an accuracy benchmark."}
