# OSTutorLLM test report

Recorded on **24 October 2026**. These checks establish functional behavior for
the tested cases, not improved student learning or universal answer accuracy.

## Automated regression suite

```bash
python -m pip install -r requirements-dev.txt
python -m unittest -v test_lessons test_groq_notes
```

**14 test methods passed.** Coverage includes:

- Failure, simpler review, retry, gated advancement and completion across all
  19 topics and 38 lesson parts.
- One correct answer does not unlock advancement.
- Invalid choices, missing IDs and duplicate/stale attempts are rejected.
- Independent sessions and 24-hour inactivity expiry.
- General quiz grading follows submitted question IDs after shuffling.
- Groq success, missing key, cache expiry and independent content copies.
- Authentication errors, rate limits, server errors and timeouts use fallback.
- Malformed, incomplete and structurally invalid notes are rejected.
- Checked examples cannot be overwritten by generated examples.
- Model-specific settings and exclusion of credentials from public responses.

Provider requests are mocked in this suite; no real key is required.

## Recorded live Groq verification

**11/11 live checks passed** through the local application, using
`openai/gpt-oss-20b` on Groq for Round Robin.

| Measurement | Final recorded run |
| --- | --- |
| Initial generation | 2.07 seconds |
| Cached topic start | 6.55 ms |
| Part-one explanation | 178 words |
| Part-one revision points | 3 |

The scenario verified the provider label, expanded notes, hidden keys, blocked
premature advancement, incorrect-answer review, a distinct simpler explanation,
correct retries, next-part content, completion and cache reuse. These are
single-run observations for one topic, not guarantees or an assessment of all
generated content.

The initially selected model was unavailable. Selecting an available model
resolved generation. Browser review caught an inconsistent scheduling example;
the application now retains checked curriculum examples.

## Lexical retrieval diagnostic

Run `python report_evaluate.py` to reproduce the 30-case diagnostic. Local
outputs are written to the ignored `.report_qa/` directory.

| Metric | Recorded result |
| --- | --- |
| Direct topic top-one matches | 12/12 (100%) |
| Paraphrased top-one matches | 7/12 (58.3%) |
| Expected topic in top three | 23/24 (95.8%) |
| Unrelated queries correctly rejected | 1/6 (16.7%) |
| Retrieval median / p95 | 0.332 / 0.559 ms |

Timing covered 1,200 local retrieval calls after warm-up and excludes HTTP,
browser rendering and generation. This small manually labelled set is
diagnostic, not a general accuracy benchmark.

## Browser verification

## Render deployment verification

The app is live at https://ostutorllm-ygh7.onrender.com on a free Python web
service. **12/12 hosted smoke checks passed**: homepage, static lesson script,
health, topics, API docs, Round Robin source retrieval, lesson start, blocked
early advancement, incorrect-answer review, a correct retry, next-part loading
and the general quiz. Groq is not yet configured on this hosted service; these
checks used built-in notes. Local Groq verification above is separate evidence.

## Browser inspection

Real Groq notes, topic selection, review after misses, correct retry, next-part
teaching, completion and same-tab refresh resume were exercised. The white and
green styling and generation notices were visually checked.

## Known limits

- Keyword retrieval still accepts many unrelated queries and confuses paraphrases.
- API minimum question length is checked before trimming, allowing a padded
  one-character input through.
- Notes and quiz wording lack comprehensive instructor review.
- No learner study, delayed-retention assessment, production load test,
  mobile-device matrix or full accessibility audit was performed.
- Sessions and caches reset on server restart.
