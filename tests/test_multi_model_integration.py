"""
Unit tests for the triple-provider (Claude, Kimi, Gemini) integration.

These tests mock the LiteLLM completion layer and verify that:
  1. Config exposes correct default model strings and provider params.
  2. CodeGeneratorAgent attaches provider-specific api_key / base_url.
  3. TaskManager cycles through providers each generation.
  4. Fallback to another provider happens when the chosen provider fails.
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import settings
from code_generator.agent import CodeGeneratorAgent
from task_manager.agent import TaskManagerAgent
from core.interfaces import TaskDefinition, Program


class TestMultiModelConfiguration(unittest.TestCase):
    def test_default_model_strings(self):
        self.assertEqual(settings.CLAUDE_MODEL, "anthropic/claude-sonnet-5")
        self.assertEqual(settings.KIMI_MODEL, "moonshot/kimi-k3")
        self.assertEqual(settings.GEMINI_MODEL, "gemini/gemini-3.1-pro-preview")

    def test_get_model_extra_params_detects_providers(self):
        with patch.object(settings, "CLAUDE_API_KEY", "claude-key"):
            with patch.object(settings, "CLAUDE_BASE_URL", "https://claude.local"):
                params = settings.get_model_extra_params("anthropic/claude-sonnet-5")
                self.assertEqual(params["api_key"], "claude-key")
                self.assertEqual(params["base_url"], "https://claude.local")

        with patch.object(settings, "KIMI_API_KEY", "kimi-key"):
            params = settings.get_model_extra_params("moonshot/kimi-k3")
            self.assertEqual(params["api_key"], "kimi-key")

        with patch.object(settings, "GEMINI_API_KEY", "gemini-key"):
            params = settings.get_model_extra_params("gemini/gemini-3.1-pro-preview")
            self.assertEqual(params["api_key"], "gemini-key")


class TestCodeGeneratorProviderParams(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.agent = CodeGeneratorAgent()

    @patch("code_generator.agent.acompletion")
    async def test_anthropic_api_key_passed(self, mock_acompletion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "def solve(): pass"
        mock_acompletion.return_value = mock_response

        with patch.object(settings, "CLAUDE_API_KEY", "my-claude-key"):
            with patch.object(settings, "CLAUDE_BASE_URL", "https://anthropic.local"):
                await self.agent.generate_code(
                    prompt="write code",
                    model_name="anthropic/claude-sonnet-5",
                    output_format="code",
                )

        mock_acompletion.assert_awaited_once()
        call_kwargs = mock_acompletion.call_args.kwargs
        self.assertEqual(call_kwargs["api_key"], "my-claude-key")
        self.assertEqual(call_kwargs["base_url"], "https://anthropic.local")


class TestTaskManagerModelCycling(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.task = TaskDefinition(
            id="test_task",
            description="Sum a list of numbers.",
            function_name_to_evolve="solve",
            input_output_examples=[{"input": [[1, 2, 3]], "output": 6}],
        )
        self.manager = TaskManagerAgent(task_definition=self.task)

    def test_model_cycle_list(self):
        self.assertEqual(
            self.manager._model_cycle,
            [settings.CLAUDE_MODEL, settings.KIMI_MODEL, settings.GEMINI_MODEL],
        )

    def test_select_generation_model_cycling(self):
        with patch.object(settings, "ENABLE_MODEL_CYCLING", True):
            gen1_secondary = self.manager._select_generation_model(1, role="secondary")
            gen1_primary = self.manager._select_generation_model(1, role="primary")
            self.assertNotEqual(gen1_secondary, gen1_primary)
            self.assertIn(gen1_secondary, self.manager._model_cycle)
            self.assertIn(gen1_primary, self.manager._model_cycle)

    def test_select_generation_model_no_cycling(self):
        with patch.object(settings, "ENABLE_MODEL_CYCLING", False):
            self.assertEqual(
                self.manager._select_generation_model(5, role="secondary"),
                settings.LLM_SECONDARY_MODEL,
            )
            self.assertEqual(
                self.manager._select_generation_model(5, role="primary"),
                settings.LLM_PRIMARY_MODEL,
            )

    @patch("task_manager.agent.CodeGeneratorAgent.execute")
    async def test_fallback_uses_other_providers(self, mock_execute):
        mock_execute.side_effect = [Exception("provider down"), "def solve(): return 6"]

        parent = Program(
            id="parent_1",
            code="def solve(): pass",
            fitness_scores={"correctness": 0.5, "runtime_ms": 1.0},
            generation=0,
            status="evaluated",
        )

        result = await self.manager._generate_with_fallback(
            prompt="fix this",
            model_name=settings.CLAUDE_MODEL,
            temperature=0.75,
            output_format="code",
        )
        self.assertEqual(result, "def solve(): return 6")
        self.assertEqual(mock_execute.await_count, 2)


if __name__ == "__main__":
    unittest.main()
