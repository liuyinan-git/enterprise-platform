"""OpenAI 兼容的聊天补全客户端（DeepSeek / 本地 Ollama 通用，零额外依赖）。"""

import json
from urllib import request
from urllib.error import HTTPError


def chat_completion(
    messages: list[dict],
    *,
    base_url: str,
    model: str,
    api_key: str = "",
    timeout: int = 60,
) -> str:
    """调用 /chat/completions，返回助手文本内容。"""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI API HTTP {exc.code}: {detail[:500]}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"AI API 响应缺少 choices: {str(data)[:500]}") from exc
