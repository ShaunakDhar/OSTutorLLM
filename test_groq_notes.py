import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
import groq_notes
from app import app, KNOWLEDGE, lesson_sessions
from lessons import LESSONS


class GroqNotesTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict('os.environ', {'GROQ_API_KEY':'test-secret-never-expose', 'GROQ_MODEL':'test-model'})
        self.env.start()
        self.addCleanup(self.env.stop)
        groq_notes._cache.clear()
        groq_notes._topic_locks.clear()
        lesson_sessions.clear()
        self.http = patch('groq_notes.httpx.Client')
        self.mock_http = self.http.start()
        self.addCleanup(self.http.stop)
        self.post = self.mock_http.return_value.__enter__.return_value.post
        self.generated = {'parts':[
            {'explanation':'Expanded teaching notes for part ' + str(i),
             'simpler':'A simple everyday analogy for part ' + str(i),
             'example':'A worked example for part ' + str(i),
             'key_points':['Important concept one', 'Important concept two', 'Important concept three']}
            for i in range(2)]}
        self.set_response(self.generated)

    def set_response(self, notes, status=200, finish='stop'):
        self.post.return_value = httpx.Response(status, request=httpx.Request('POST', groq_notes.ENDPOINT),
            json={'choices':[{'finish_reason':finish, 'message':{'content':json.dumps(notes)}}]})

    def notes(self):
        return groq_notes.topic_notes(KNOWLEDGE[0], LESSONS['OS-01'])

    def test_generation_keeps_quiz_and_core_outline(self):
        result = self.notes()
        self.assertEqual(result['provider'], 'groq')
        self.assertEqual(result['model'], 'test-model')
        self.assertEqual(result['parts'][0]['explanation'], self.generated['parts'][0]['explanation'])
        self.assertEqual(result['parts'][0]['questions'], LESSONS['OS-01'][0]['questions'])
        self.assertEqual(result['parts'][0]['title'], LESSONS['OS-01'][0]['title'])
        self.assertEqual(result['parts'][0]['example'], LESSONS['OS-01'][0]['example'])
        payload = self.post.call_args.kwargs['json']
        self.assertEqual(payload['response_format'], {'type':'json_object'})
        self.assertNotIn('test-secret-never-expose', json.dumps(payload))
        self.assertEqual(self.post.call_args.args[0], groq_notes.ENDPOINT)

    def test_missing_key_uses_builtin_without_network(self):
        with patch.dict('os.environ', {'GROQ_API_KEY':''}):
            result = self.notes()
        self.assertEqual(result['provider'], 'built-in')
        self.post.assert_not_called()

    def test_gpt_oss_request_limits_reasoning_and_hides_it(self):
        with patch.dict('os.environ', {'GROQ_MODEL':'openai/gpt-oss-20b'}):
            self.assertEqual(self.notes()['provider'], 'groq')
        payload = self.post.call_args.kwargs['json']
        self.assertEqual(payload['reasoning_effort'], 'low')
        self.assertIs(payload['include_reasoning'], False)
        self.assertEqual(payload['max_completion_tokens'], 4000)

    def test_cache_reuses_success_and_does_not_share_mutable_parts(self):
        first = self.notes()
        first['parts'][0]['explanation'] = 'mutated'
        second = self.notes()
        self.assertEqual(self.post.call_count, 1)
        self.assertNotEqual(second['parts'][0]['explanation'], 'mutated')
        key = ('OS-01', 'test-model')
        timestamp, value = groq_notes._cache[key]
        groq_notes._cache[key] = (timestamp - 3601, value)
        self.notes()
        self.assertEqual(self.post.call_count, 2)

    def test_auth_rate_limit_and_server_errors_fall_back(self):
        for status in [401, 429, 500]:
            with self.subTest(status=status):
                self.set_response({}, status=status)
                self.assertEqual(self.notes()['provider'], 'built-in')
                self.assertFalse(groq_notes._cache)

    def test_timeout_falls_back_and_does_not_cache_failure(self):
        self.post.side_effect = httpx.ReadTimeout('provider details test-secret-never-expose')
        result = self.notes()
        self.assertEqual(result['provider'], 'built-in')
        self.assertNotIn('test-secret-never-expose', json.dumps(result))
        self.assertFalse(groq_notes._cache)
        self.post.side_effect = None
        self.assertEqual(self.notes()['provider'], 'groq')

    def test_malformed_incomplete_or_wrong_shape_is_rejected(self):
        cases = [{}, {'parts':[]}, {'parts':[{}]*2},
                 {'parts':[dict(p, key_points=['only one']) for p in self.generated['parts']]},
                 {'parts':[dict(p, explanation=' ') for p in self.generated['parts']]},
                 {'parts':[dict(p, unexpected='extra') for p in self.generated['parts']]}]
        for bad in cases:
            self.set_response(bad)
            self.assertEqual(self.notes()['provider'], 'built-in')
        self.set_response(self.generated, finish='length')
        self.assertEqual(self.notes()['provider'], 'built-in')
        self.post.return_value = httpx.Response(200, request=httpx.Request('POST', groq_notes.ENDPOINT),
            json={'choices':[{'finish_reason':'stop','message':{'content':'not json'}}]})
        self.assertEqual(self.notes()['provider'], 'built-in')

    def test_generated_lesson_review_uses_simpler_notes_and_grading_stays_local(self):
        client = TestClient(app)
        view = client.post('/api/lessons/start', json={'topic_id':'OS-01'}).json()
        self.assertEqual(view['notes_provider'], 'groq')
        self.assertEqual(view['key_points'], self.generated['parts'][0]['key_points'])
        authored = LESSONS['OS-01'][0]['questions']
        wrong = {q['id']:q['options'].index(authored[int(q['id'])][2]) for q in view['questions']}
        result = client.post(f"/api/lessons/{view['session_id']}/check", json={
            'part_index':0,'attempt':0,'answers':wrong}).json()
        self.assertFalse(result['passed'])
        self.assertEqual(result['lesson']['simpler'], self.generated['parts'][0]['simpler'])
        self.assertEqual(self.post.call_count, 1)  # retries and grading do not call Groq
        public = json.dumps([view, result, client.get('/api/health').json()])
        self.assertNotIn('test-secret-never-expose', public)
        self.assertTrue(all('answer' not in q for q in view['questions']))


if __name__ == '__main__':
    unittest.main()
