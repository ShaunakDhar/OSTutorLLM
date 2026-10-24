"""Generate grounded lesson notes on the server; never expose credentials."""
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Annotated

from dotenv import load_dotenv
import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

load_dotenv(Path(__file__).resolve().parent / '.env', override=False)
logger = logging.getLogger(__name__)
DEFAULT_MODEL = 'openai/gpt-oss-20b'
ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)]
Point = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=400)]


class GeneratedPart(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    explanation: Text
    simpler: Text
    example: Text
    key_points: list[Point] = Field(min_length=3, max_length=5)


class GeneratedNotes(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    parts: list[GeneratedPart] = Field(min_length=2, max_length=2)


_cache = {}
_cache_lock = Lock()
_topic_locks = {}


def notes_configuration():
    return {'configured': bool(os.getenv('GROQ_API_KEY', '').strip()),
            'model': os.getenv('GROQ_MODEL', '').strip() or DEFAULT_MODEL}


def topic_notes(topic, curriculum):
    """Return a session snapshot. Only successful generations are cached (1 hour)."""
    fallback = {'parts':deepcopy(curriculum), 'provider':'built-in', 'model':None,
                'notice':'Built-in notes. Groq notes are not configured yet.'}
    config = notes_configuration()
    if not config['configured']:
        return fallback
    cache_key = (topic['id'], config['model'])
    with _cache_lock:
        # The app only calls this for its 19 curated topics.
        topic_lock = _topic_locks.setdefault(cache_key, Lock())
    with topic_lock:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and monotonic() - cached[0] < 3600:
                return deepcopy(cached[1])
        prompt = {
            'topic':topic['topic'], 'reference_notes':topic['content'],
            'lesson_parts':curriculum,
            'output_shape':{'parts':[{'explanation':'150–220 words in short plain-text paragraphs',
                                     'simpler':'An easier explanation in 60–100 words, using a familiar analogy and mapping it back to the concept',
                                     'example':'Copy the supplied lesson example exactly; do not add invented timings or processes',
                                     'key_points':['3 to 5 concise revision points']}]},
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(30, connect=5), follow_redirects=False) as client:
                response = client.post(ENDPOINT,
                    headers={'Authorization':'Bearer ' + os.environ['GROQ_API_KEY'].strip()},
                    json={'model':config['model'], 'temperature':0.3, 'max_completion_tokens':4000,
                          **({'reasoning_effort':'low', 'include_reasoning':False}
                             if config['model'] in ('openai/gpt-oss-20b', 'openai/gpt-oss-120b') else {}),
                          'response_format':{'type':'json_object'},
                          'messages':[
                              {'role':'system', 'content':
                               'You are a careful Operating Systems teacher helping a beginner. '
                               'Return only a JSON object with exactly two parts, in the same order as lesson_parts. '
                               'Each part must have only explanation, simpler, example, key_points. '
                               'Expand the supplied facts into clear teaching notes. Define technical terms before using them. '
                               'Teach every fact required by that part’s quiz; preserve the supplied correct answers. '
                               'Do not change the scope or invent citations, sources or performance claims. '
                               'Use the supplied worked example verbatim. Do not invent extra processes, timings or calculations. '
                               'Use plain text, not Markdown or HTML. Keep each part focused and mathematically correct. '
                               'The simpler explanation must use easier wording and an everyday analogy, not repeat the explanation.'},
                              {'role':'user','content':json.dumps(prompt, ensure_ascii=False)}]})
                response.raise_for_status()
                payload = response.json()
            choice = payload['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('Incomplete generation')
            generated = GeneratedNotes.model_validate_json(choice['message']['content'])
            parts = deepcopy(curriculum)
            for part, notes in zip(parts, generated.parts):
                # Keep the checked worked example as the numerical anchor;
                # generated notes must not replace it with inconsistent math.
                part.update(notes.model_dump(exclude={'example'}))
            result = {'parts':parts, 'provider':'groq', 'model':config['model'],
                      'notice':'AI-assisted notes generated with Groq from the topic outline. Review important details against your course material.'}
            with _cache_lock:
                _cache[cache_key] = (monotonic(), deepcopy(result))
            return result
        except (httpx.HTTPError, ValidationError, ValueError, KeyError, IndexError, TypeError):
            # Never log request headers, API responses, or exception text: they
            # may contain credentials or provider-specific internal details.
            logger.warning('Groq notes unavailable; using built-in notes for %s', topic['id'])
            fallback['notice'] = 'Groq notes are unavailable right now. You can continue with the built-in notes and quizzes.'
            return fallback
