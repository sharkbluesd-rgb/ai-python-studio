from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from ai_assistant import AIProviderError, generate_reply


class AIAssistantTests(unittest.TestCase):
    def test_rejects_unknown_provider(self):
        with self.assertRaises(AIProviderError):
            generate_reply(provider="other", api_key="x", model="m", prompt="hello")

    def test_rejects_empty_prompt(self):
        with self.assertRaises(AIProviderError):
            generate_reply(provider="gemini", api_key="x", model="m", prompt=" ")

    @patch("ai_assistant._post_json")
    def test_gemini_response(self, post):
        post.return_value = {"candidates": [{"content": {"parts": [{"text": "مرحبا"}]}}]}
        answer = generate_reply(provider="gemini", api_key="secret", model="gemini-2.5-flash", prompt="hi", system_instruction="safe")
        self.assertEqual(answer, "مرحبا")
        args = post.call_args
        self.assertIn("x-goog-api-key", args.args[2])
        self.assertEqual(args.args[2]["x-goog-api-key"], "secret")
        self.assertEqual(args.args[1]["systemInstruction"]["parts"][0]["text"], "safe")

    @patch("ai_assistant._post_json")
    def test_openai_response(self, post):
        post.return_value = {"choices": [{"message": {"content": "Hello"}}]}
        answer = generate_reply(provider="openai", api_key="secret", model="gpt-4.1-mini", prompt="hi", system_instruction="safe")
        self.assertEqual(answer, "Hello")
        self.assertEqual(post.call_args.args[1]["messages"][0]["role"], "system")

    @patch("ai_assistant._post_json")
    def test_missing_provider_text_is_safe_error(self, post):
        post.return_value = {}
        with self.assertRaises(AIProviderError):
            generate_reply(provider="openai", api_key="secret", model="m", prompt="hi")


if __name__ == "__main__":
    unittest.main()
