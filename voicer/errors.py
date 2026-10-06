"""CLI validation errors and safe, actionable OpenAI error messages."""

import re

import httpx2
import openai


class CliError(ValueError):
    pass


def format_openai_error(
    error: openai.OpenAIError | httpx2.RequestError,
    *,
    request_id: str | None = None,
) -> str:
    body = getattr(error, "body", None)
    error_body = body if isinstance(body, dict) else {}
    if isinstance(error_body.get("error"), dict):
        error_body = error_body["error"]
    status = getattr(error, "status_code", None)
    quota = any(
        value == "insufficient_quota"
        for value in (
            error_body.get("code"),
            error_body.get("type"),
            getattr(error, "code", None),
            getattr(error, "type", None),
        )
    )

    if status == 429 and quota:
        message = (
            "OpenAI quota exceeded. Check your plan and billing details. "
            "OpenAI error code/type: insufficient_quota."
        )
    elif isinstance(error, (openai.APITimeoutError, httpx2.TimeoutException)):
        message = "OpenAI request or audio download timed out. Try again."
    elif isinstance(error, (openai.APIConnectionError, httpx2.RequestError)):
        message = (
            "OpenAI connection or audio stream failed. "
            "Check your network connection and try again."
        )
    elif status == 401:
        message = "OpenAI authentication failed. Check OPENAI_API_KEY."
    elif status == 403:
        message = "OpenAI permission denied. Check project and model access."
    elif status == 429:
        message = "OpenAI rate limit exceeded. Wait before trying again."
    elif status in (400, 422):
        kind = "bad request" if status == 400 else "invalid request"
        message = (
            f"OpenAI {kind}. Check the text length, model, voice, audio format, "
            "instructions and speed."
        )
    elif isinstance(status, int) and status >= 500:
        message = f"OpenAI server error (HTTP {status}). Try again later."
    elif isinstance(status, int):
        message = f"OpenAI request failed (HTTP {status}). Check request settings."
    else:
        message = "OpenAI request failed. Check request settings and try again."

    # SDK messages/bodies can echo credentials or input; report only safe metadata.
    request_id = getattr(error, "request_id", None) or request_id
    if isinstance(request_id, str) and re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", request_id
    ):
        message += f" Request ID: {request_id}."
    return message
