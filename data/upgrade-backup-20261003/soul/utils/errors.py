from __future__ import annotations

import asyncio

def friendly_error(error: Exception) -> str:
    code = getattr(error, "code", None)
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return "The request timed out. Please try again."
    if code in (401, 403):
        return "Gemini rejected access. Check your API key and model permissions."
    if code == 404:
        return "The configured model was not found. Check /models and your .env."
    if code == 429:
        return "Gemini rate limit or quota reached. Wait and check your quota."
    if code in (500, 502, 503, 504):
        return "Gemini is temporarily unavailable. Please try again shortly. Completed actions are not rolled back."
    if code == 400:
        return "Gemini rejected the request. Check the API key and model configuration."
    return "The operation failed. Check connectivity and configuration; details are in data/soul.log."
