import ast
import importlib
import os
import unittest
from unittest.mock import AsyncMock, patch

from config import settings


class SettingsRegressionTests(unittest.TestCase):
    def test_litellm_env_values_are_coerced(self):
        original = {name: os.environ.get(name) for name in (
            "LITELLM_MAX_TOKENS",
            "LITELLM_TEMPERATURE",
            "LITELLM_TOP_P",
            "LITELLM_TOP_K",
        )}
        try:
            os.environ["LITELLM_MAX_TOKENS"] = "256"
            os.environ["LITELLM_TEMPERATURE"] = "0.3"
            os.environ["LITELLM_TOP_P"] = "0.9"
            os.environ["LITELLM_TOP_K"] = "40"
            import config.settings as settings_module
            importlib.reload(settings_module)
            self.assertEqual(settings_module.LITELLM_MAX_TOKENS, 256)
            self.assertEqual(settings_module.LITELLM_TOP_K, 40)
            self.assertEqual(settings_module.LITELLM_TEMPERATURE, 0.3)
            self.assertEqual(settings_module.LITELLM_TOP_P, 0.9)
        finally:
            for name, value in original.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            importlib.reload(settings)


class CodeGeneratorRegressionTests(unittest.IsolatedAsyncioTestCase):
    @patch("code_generator.agent.acompletion", new_callable=AsyncMock)
    async def test_none_generation_params_are_not_forwarded(self, mock_acompletion):
        from code_generator.agent import CodeGeneratorAgent

        mock_message = type("Message", (), {"content": "print('ok')"})()
        mock_choice = type("Choice", (), {"message": mock_message})()
        mock_acompletion.return_value = type("Response", (), {"choices": [mock_choice]})()

        agent = CodeGeneratorAgent()
        agent.generation_config = {
            "temperature": None,
            "top_p": None,
            "top_k": 20,
            "max_tokens": None,
        }
        agent.litellm_extra_params = {"base_url": None, "api_base": "https://example.invalid"}

        await agent.generate_code("hi")

        kwargs = mock_acompletion.await_args.kwargs
        self.assertNotIn("temperature", kwargs)
        self.assertNotIn("top_p", kwargs)
        self.assertNotIn("max_tokens", kwargs)
        self.assertNotIn("base_url", kwargs)
        self.assertEqual(kwargs["top_k"], 20)
        self.assertEqual(kwargs["api_base"], "https://example.invalid")


class TaskManagerMainOrderRegressionTests(unittest.TestCase):
    def test_sample_task_is_defined_before_task_manager_uses_it(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(repo_root, "task_manager", "agent.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)

        sample_task_line = None
        task_manager_line = None

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "sample_task":
                        sample_task_line = node.lineno
                    if isinstance(target, ast.Name) and target.id == "task_manager":
                        call = node.value
                        if (
                            isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Name)
                            and call.func.id == "TaskManagerAgent"
                        ):
                            task_manager_line = node.lineno

        self.assertIsNotNone(sample_task_line)
        self.assertIsNotNone(task_manager_line)
        self.assertLess(sample_task_line, task_manager_line)
