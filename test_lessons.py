"""Run with: python -m unittest -v test_lessons"""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app, KNOWLEDGE, QUIZ, lesson_sessions
from lessons import LESSONS


class GuidedLessonTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict('os.environ', {'GROQ_API_KEY':''})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        lesson_sessions.clear()
        self.client = TestClient(app)

    def start(self, topic='OS-01'):
        response = self.client.post('/api/lessons/start', json={'topic_id':topic})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def submit(self, view, wrong=False):
        # Build the answer key from the authored curriculum, independently of
        # the shuffled options and private session answer indices.
        authored = LESSONS[view['topic_id']][view['part_index']]['questions']
        answers = {}
        for question in view['questions']:
            target = authored[int(question['id'])][2 if wrong else 1]
            answers[question['id']] = question['options'].index(target)
        return self.client.post(f"/api/lessons/{view['session_id']}/check", json={
            'part_index':view['part_index'], 'attempt':view['attempt'], 'answers':answers})

    def test_every_topic_review_retry_progress_and_complete(self):
        self.assertEqual(set(LESSONS), {topic['id'] for topic in KNOWLEDGE})
        for topic in LESSONS:
            with self.subTest(topic=topic):
                view = self.start(topic)
                for index, authored in enumerate(LESSONS[topic]):
                    self.assertEqual(view['part_index'], index)
                    self.assertEqual(view['phase'], 'learn')
                    self.assertTrue(all('answer' not in q for q in view['questions']))
                    self.assertEqual(self.client.post(f"/api/lessons/{view['session_id']}/next").status_code, 409)
                    response = self.submit(view, wrong=True)
                    self.assertEqual(response.status_code, 200)
                    failed = response.json()
                    self.assertEqual(failed['score'], 0)
                    self.assertFalse(failed['passed'])
                    reviewed = failed['lesson']
                    self.assertEqual(reviewed['phase'], 'review')
                    self.assertEqual(reviewed['part_index'], index)
                    self.assertEqual(reviewed['simpler'], authored['simpler'])
                    self.assertNotEqual(reviewed['simpler'], reviewed['explanation'])
                    self.assertEqual(self.submit(view).status_code, 409)  # old attempt
                    passed = self.submit(reviewed).json()
                    self.assertTrue(passed['passed'])
                    self.assertEqual(passed['score'], 2)
                    self.assertEqual(self.submit(reviewed).status_code, 409)  # duplicate
                    saved = self.client.get(f"/api/lessons/{view['session_id']}").json()
                    self.assertEqual(saved['phase'], passed['lesson']['phase'])
                    if index < len(LESSONS[topic])-1:
                        view = self.client.post(f"/api/lessons/{view['session_id']}/next").json()
                    else:
                        self.assertEqual(saved['phase'], 'complete')
                        self.assertEqual(saved['completed_parts'], len(LESSONS[topic]))
                        self.assertEqual(self.client.post(f"/api/lessons/{view['session_id']}/next").status_code, 409)

    def test_one_correct_answer_does_not_unlock_next_part(self):
        view = self.start()
        authored = LESSONS['OS-01'][0]['questions']
        answers = {q['id']: q['options'].index(authored[int(q['id'])][1 if q['id']=='0' else 2]) for q in view['questions']}
        result = self.client.post(f"/api/lessons/{view['session_id']}/check", json={'part_index':0,'attempt':0,'answers':answers}).json()
        self.assertEqual(result['score'], 1)
        self.assertFalse(result['passed'])
        self.assertEqual(self.client.post(f"/api/lessons/{view['session_id']}/next").status_code, 409)

    def test_invalid_requests_do_not_change_progress(self):
        self.assertEqual(self.client.post('/api/lessons/start', json={'topic_id':'missing'}).status_code, 404)
        self.assertEqual(self.client.get('/api/lessons/missing').status_code, 404)
        view = self.start()
        path = f"/api/lessons/{view['session_id']}/check"
        for answers in [{'0':0}, {'0':0,'1':9}, {'0':True,'1':0}, {'0':'0','1':0}, {'x':0,'y':1}]:
            self.assertEqual(self.client.post(path, json={'part_index':0,'attempt':0,'answers':answers}).status_code, 422)
        self.assertEqual(lesson_sessions[view['session_id']]['attempt'], 0)

    def test_sessions_are_independent_and_expire(self):
        first = self.start()
        second = self.start('OS-05')
        self.submit(first)
        self.assertEqual(self.client.get(f"/api/lessons/{second['session_id']}").json()['phase'], 'learn')
        lesson_sessions[first['session_id']]['touched'] -= 86401
        self.assertEqual(self.client.get(f"/api/lessons/{first['session_id']}").status_code, 404)

    def test_general_quiz_grades_shuffled_question_ids(self):
        key = {q['id']:q['answer'] for q in QUIZ}
        # Reverse order makes the regression deterministic.
        ids = list(reversed(key))
        result = self.client.post('/api/quiz/submit', json={'question_ids':ids,'answers':[key[qid] for qid in ids]})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['score'], 8)
        self.assertEqual([r['id'] for r in result.json()['results']], ids)
        self.assertEqual(self.client.post('/api/quiz/submit', json={'question_ids':['Q1']*8,'answers':[0]*8}).status_code, 422)

    def test_existing_endpoints_still_work(self):
        for path in ['/', '/api/health', '/api/topics', '/api/metrics', '/static/lessons.js']:
            self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.post('/api/ask', json={'question':'Explain Round Robin scheduling'})
        self.assertEqual(response.json()['sources'][0]['id'], 'OS-01')


if __name__ == '__main__':
    unittest.main()
