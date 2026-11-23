"""Minimal, bounded AI provider adapters for the in-app coding assistant.

API keys are passed per request and are never persisted or logged.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class AIProviderError(RuntimeError):
    """Safe, user-displayable provider failure."""


def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise AIProviderError("استجابة المزود تجاوزت الحد المسموح.")
            result = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not include response bodies; providers may echo sensitive data.
        if exc.code in (401, 403):
            raise AIProviderError("رفض المزود مفتاح API أو صلاحياته (401/403).") from exc
        if exc.code == 429:
            raise AIProviderError("وصلت إلى حد طلبات المزود (429). حاول لاحقاً.") from exc
        raise AIProviderError(f"فشل طلب المزود برمز HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise AIProviderError("تعذر الاتصال بمزود الذكاء الاصطناعي. تحقق من الإنترنت.") from exc
    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AIProviderError("انتهت مهلة الاتصال أو أرسل المزود استجابة غير صالحة.") from exc
    if not isinstance(result, dict):
        raise AIProviderError("استجابة المزود غير صالحة.")
    return result


def generate_reply(
    *,
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout: int = 45,
) -> str:
    """Send a user-approved prompt to Gemini or OpenAI and return bounded text."""
    provider = provider.strip().lower()
    api_key = api_key.strip()
    model = model.strip()
    if provider not in {"gemini", "openai"}:
        raise AIProviderError("مزود الذكاء الاصطناعي غير مدعوم.")
    if not api_key or len(api_key) > 4096:
        raise AIProviderError("مفتاح API فارغ أو غير صالح.")
    if not model or len(model) > 128:
        raise AIProviderError("اسم النموذج غير صالح.")
    if not prompt.strip() or len(prompt) > 40_000:
        raise AIProviderError("نص الطلب فارغ أو يتجاوز الحد المسموح.")
    timeout = max(5, min(int(timeout), 90))

    if provider == "gemini":
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + urllib.parse.quote(model, safe="")
            + ":generateContent"
        )
        data = _post_json(
            url,
            {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"maxOutputTokens": 4096, "temperature": 0.2}},
            {"x-goog-api-key": api_key},
            timeout,
        )
        try:
            answer = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("لم يُرجع Gemini نصاً قابلاً للعرض.") from exc
    else:
        url = "https://api.openai.com/v1/chat/completions"
        data = _post_json(
            url,
            {"model": model, "messages": [{"role": "user", "content": prompt}],
             "max_tokens": 4096, "temperature": 0.2},
            {"Authorization": f"Bearer {api_key}"},
            timeout,
        )
        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("لم يُرجع OpenAI نصاً قابلاً للعرض.") from exc
    if not isinstance(answer, str) or not answer.strip():
        raise AIProviderError("رد المزود فارغ.")
    return answer[:40_000]
