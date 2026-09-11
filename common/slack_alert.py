import json
import os
import traceback
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict

from common.logger import Logger


class SlackAlert:
    """Posts an exception to Slack through an incoming webhook (SLACK_WEBHOOK_URL). Does nothing if it is not set."""

    @classmethod
    def send(cls, exception: Exception) -> None:
        """Error alert with message and traceback."""
        cls._post(cls._build_message_payload(exception))

    @classmethod
    def send_message(cls, text: str) -> None:
        """Plain status message (e.g. migration paused / resumed)."""
        cls._post({"text": f"*migration:* {text}"})

    @classmethod
    def _post(cls, payload: Dict[str, Any]) -> None:
        url = os.getenv("SLACK_WEBHOOK_URL")
        if not url:
            Logger.warning("SLACK_WEBHOOK_URL is not set - skipping Slack alert")
            return

        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(request, timeout=10)
        except Exception as err:  # never let a failed alert hide the original error or stop the run
            Logger.error(f"Slack alert failed: {err}")

    @classmethod
    def _build_message_payload(cls, exception: Exception) -> Dict[str, Any]:
        error_type = exception.__class__.__name__
        error_message = str(exception)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
        text = f"🚨 *ERROR ALERT: {error_type}* 🚨"

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": text}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "<!channel> *Critical error detected!*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Error Message:*\n```{error_message}```"}},
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": "*Service:*\n`migration`"},
                    {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
                ],
            },
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Traceback:*"}},
        ]

        tb_text = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        max_block_size = 2900
        for i in range(0, len(tb_text), max_block_size):
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": f"```{tb_text[i:i + max_block_size]}```"}}
            )

        return {"text": text, "blocks": blocks}
