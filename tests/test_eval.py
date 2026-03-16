"""Run ADK evaluations via pytest.

Wraps the ADK AgentEvaluator to run structured evaluation test sets
defined in .test.json files. These test tool trajectory correctness
(did the agent call the right tools in the right order?) and response
quality (did the agent produce a good narration for the user?).

Run with: pytest tests/test_eval.py -v
Or via CLI: adk eval noor_agent tests/eval/navigation_eval.test.json \
    --config_file_path tests/eval/test_config.json --print_detailed_results
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

import pytest

_has_api_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"))
api = pytest.mark.skipif(not _has_api_key, reason="No Gemini API credentials available")


@api
class TestADKEvaluation:
    """Run ADK evaluation test sets against the Noor agent."""

    async def test_navigation_eval(self):
        """Run navigation eval set — tool trajectory for browser actions."""
        from google.adk.evaluation.agent_evaluator import AgentEvaluator

        await AgentEvaluator.evaluate(
            agent_module="noor_agent",
            eval_dataset_file_path_or_dir="tests/eval/navigation_eval.test.json",
        )

    async def test_summarization_eval(self):
        """Run summarization eval set — tool trajectory for content reading."""
        from google.adk.evaluation.agent_evaluator import AgentEvaluator

        await AgentEvaluator.evaluate(
            agent_module="noor_agent",
            eval_dataset_file_path_or_dir="tests/eval/summarization_eval.test.json",
        )
