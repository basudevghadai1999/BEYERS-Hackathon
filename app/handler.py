"""Lambda entry point — receives EventBridge alarm events and runs the Commander agent."""

import asyncio
import json
import logging
import os
from typing import Any, Dict

from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.commander import commander_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

APP_NAME = "aic-commander"
USER_ID = "system"


async def _run_commander(event: dict) -> dict:
    """Run the Commander agent with the alarm event and collect the final response."""
    runner = InMemoryRunner(agent=commander_agent, app_name=APP_NAME)

    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    # Format the event as a user message to the Commander
    prompt = (
        "A CloudWatch alarm has fired. Here is the raw event:\n\n"
        f"```json\n{json.dumps(event, indent=2, default=str)}\n```\n\n"
        "Execute the full incident investigation: DETECT → PLAN → INVESTIGATE → DECIDE → REPORT."
    )

    content = types.Content(
        role="user", parts=[types.Part(text=prompt)]
    )

    final_text = ""
    async for event_response in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=content
    ):
        if event_response.is_final_response() and event_response.content and event_response.content.parts:
            for part in event_response.content.parts:
                if part.text:
                    final_text += part.text

    return {
        "response": final_text,
        "session_id": session.id,
    }


def lambda_handler(event: Any, context: Any = None) -> Dict[str, Any]:
    """AWS Lambda entry point.

    Handles both EventBridge alarm events and direct test invocations.
    """
    logger.info("Received event: %s", json.dumps(event, default=str)[:500])

    # Normalize: if this is an EventBridge event, it has 'detail-type'
    # If it's a direct invoke with just the alarm detail, wrap it
    if "detail-type" not in event and "detail" not in event:
        # Assume it's a raw alarm detail passed directly for testing
        event = {"detail": event, "detail-type": "CloudWatch Alarm State Change"}

    try:
        result = asyncio.run(_run_commander(event))
        logger.info("Commander completed successfully")
        return {
            "statusCode": 200,
            "body": result,
        }
    except Exception as e:
        logger.exception("Commander failed: %s", e)
        return {
            "statusCode": 500,
            "body": {"error": str(e)},
        }
