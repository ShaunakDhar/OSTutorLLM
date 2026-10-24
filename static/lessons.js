let currentLesson = null;
let lessonGeneration = 0;
const lessonStorageKey = 'ostutor-guided-session';

function lessonNode(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function rememberLesson(id) {
  try { if (id) sessionStorage.setItem(lessonStorageKey, id); else sessionStorage.removeItem(lessonStorageKey); } catch {}
}
function lessonButton(label, action) {
  const button = lessonNode('button', label);
  button.type = 'button';
  button.onclick = action;
  return button;
}
async function startLesson(topicId) {
  const generation = ++lessonGeneration;
  currentLesson = null;
  rememberLesson(null);
  $('lessonBody').replaceChildren();
  $('lessonStatus').textContent = 'Preparing your topic notes… This can take a few seconds.';
  $('guidedLesson').scrollIntoView({behavior: 'smooth', block: 'start'});
  try {
    const data = await api('/api/lessons/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({topic_id:topicId})});
    if (generation !== lessonGeneration) return;
    rememberLesson(data.session_id);
    renderLesson(data);
  } catch (error) {
    if (generation === lessonGeneration) $('lessonStatus').textContent = 'Could not start the lesson: ' + error.message + ' Select a topic to try again.';
  }
}
async function resumeLesson() {
  let id;
  try { id = sessionStorage.getItem(lessonStorageKey); } catch {}
  if (!id) return;
  const generation = lessonGeneration;
  try {
    const data = await api('/api/lessons/' + encodeURIComponent(id));
    if (generation === lessonGeneration) renderLesson(data);
  } catch {
    if (generation === lessonGeneration) {
      rememberLesson(null);
      $('lessonStatus').textContent = 'Your previous lesson is unavailable. Choose a topic to start again.';
    }
  }
}
function renderLesson(data, feedback = null) {
  currentLesson = data;
  document.querySelectorAll('[data-topic-id]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.topicId === data.topic_id)));
  const body = $('lessonBody');
  body.replaceChildren();
  $('lessonStatus').textContent = `${data.topic} · Part ${data.part_index + 1} of ${data.total_parts} · ${data.completed_parts}/${data.total_parts} parts mastered`;
  const progress = document.createElement('progress');
  progress.max = data.total_parts;
  progress.value = data.completed_parts;
  progress.setAttribute('aria-label', 'Parts mastered');
  progress.style.width = '100%';
  body.append(progress, lessonNode('p', data.notes_notice, 'muted'));
  body.append(lessonNode('h3', data.title));
  data.explanation.split(/\n\s*\n/).filter(Boolean).forEach(text => body.append(lessonNode('p', text)));
  if (data.key_points && data.key_points.length) {
    body.append(lessonNode('h3', 'Key points to remember'));
    const points = lessonNode('ul');
    data.key_points.forEach(text => points.append(lessonNode('li', text)));
    body.append(points);
  }
  body.append(lessonNode('p', 'Example: ' + data.example, 'notice'));
  body.append(lessonNode('p', 'Topic reference: ' + data.source, 'muted'));
  if (feedback) {
    const result = lessonNode('div', null, 'result');
    result.append(lessonNode('h3', `You scored ${feedback.score}/${feedback.total}`, feedback.passed ? 'good' : 'bad'));
    feedback.results.forEach(item => {
      result.append(lessonNode('p', `${item.correct ? '✓' : 'Review'} ${item.question}`));
      if (!item.correct) result.append(lessonNode('p', `You chose: ${item.selected_answer}. Correct answer: ${item.correct_answer}.`));
    });
    body.append(result);
  }
  if (data.phase === 'complete') {
    body.append(lessonNode('h3', 'Topic complete! You have mastered every part.', 'good'));
    body.append(lessonNode('p', 'Choose another topic above, or revisit this one.'));
    body.append(lessonButton('Study this topic again', () => startLesson(data.topic_id)));
  } else if (data.phase === 'passed') {
    body.append(lessonNode('p', 'Both answers correct. You are ready for the next part.', 'good'));
    body.append(lessonButton('Learn next part', event => advanceLesson(event.currentTarget)));
  } else {
    if (data.phase === 'review') {
      body.append(lessonNode('h3', 'Let’s make it simpler'));
      body.append(lessonNode('p', data.simpler, 'notice'));
      body.append(lessonNode('p', 'Take your time. Read the example again, then try both questions. You can retry as often as you need.'));
    }
    const area = lessonNode('div');
    const button = lessonButton(data.phase === 'review' ? 'Try the short quiz again' : 'I’m ready for the short quiz', () => {
      button.hidden = true;
      renderLessonQuiz(area, data);
    });
    body.append(button, area);
  }
}
function renderLessonQuiz(area, data) {
  area.replaceChildren();
  const form = document.createElement('form');
  form.append(lessonNode('p', 'Answer both questions correctly to continue.'));
  data.questions.forEach((question, index) => {
    const field = lessonNode('fieldset', null, 'question');
    field.append(lessonNode('legend', `${index + 1}. ${question.q}`));
    question.options.forEach((option, choice) => {
      const label = lessonNode('label', null, 'option');
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'lesson-' + question.id;
      radio.value = choice;
      radio.required = true;
      label.append(radio, document.createTextNode(option));
      field.append(label);
    });
    form.append(field);
  });
  const status = lessonNode('p');
  status.setAttribute('role', 'status');
  const submit = lessonNode('button', 'Check my understanding');
  submit.type = 'submit';
  form.append(submit, status);
  form.onsubmit = async event => {
    event.preventDefault();
    const generation = lessonGeneration;
    const values = new FormData(form);
    const answers = Object.fromEntries(data.questions.map(q => [q.id, Number(values.get('lesson-' + q.id))]));
    submit.disabled = true;
    status.textContent = 'Checking your answers…';
    try {
      const result = await api(`/api/lessons/${data.session_id}/check`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({part_index:data.part_index, attempt:data.attempt, answers})});
      if (generation !== lessonGeneration) return;
      renderLesson(result.lesson, result);
      $('guidedLesson').scrollIntoView({behavior:'smooth', block:'start'});
    } catch (error) {
      if (generation !== lessonGeneration) return;
      status.textContent = 'Could not check answers: ' + error.message;
      submit.disabled = false;
    }
  };
  area.append(form);
}
async function advanceLesson(button) {
  const generation = lessonGeneration;
  button.disabled = true;
  try {
    const data = await api(`/api/lessons/${currentLesson.session_id}/next`, {method:'POST'});
    if (generation !== lessonGeneration) return;
    renderLesson(data);
    $('guidedLesson').scrollIntoView({behavior:'smooth', block:'start'});
  } catch (error) {
    if (generation !== lessonGeneration) return;
    $('lessonStatus').textContent = 'Could not load the next part: ' + error.message;
    button.disabled = false;
  }
}
