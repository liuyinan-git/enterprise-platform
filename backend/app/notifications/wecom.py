"""企业微信「自建应用」消息发送。

流程：corpid + corpsecret 换取 access_token（内存缓存，7200s 过期），
再调用 message/send 向指定应用成员发送 Markdown 消息。
"""

import json
import time
from urllib import request

TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/message/send"

# 进程内 token 缓存（key 由 corpid+corpsecret 决定，避免误用其它企业）
_token_cache: dict[str, tuple[str, float]] = {}


def get_access_token(corpid: str, corpsecret: str, timeout: int = 5) -> str:
    """获取 access_token，命中缓存则直接返回。"""
    cache_key = f"{corpid}|{corpsecret}"
    cached = _token_cache.get(cache_key)
    if cached and cached[1] > time.time() + 60:
        return cached[0]

    url = f"{TOKEN_URL}?corpid={corpid}&corpsecret={corpsecret}"
    with request.urlopen(url, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errcode") != 0:
        raise RuntimeError(f"WeCom gettoken failed: errcode={result.get('errcode')} errmsg={result.get('errmsg')}")

    token = result["access_token"]
    expires_in = int(result.get("expires_in", 7200))
    _token_cache[cache_key] = (token, time.time() + expires_in)
    return token


def send_markdown(
    corpid: str,
    corpsecret: str,
    agentid: int,
    touser: str,
    content: str,
    timeout: int = 5,
) -> dict:
    """向企业微信应用成员发送 Markdown 消息，返回微信返回的 JSON。"""
    token = get_access_token(corpid, corpsecret, timeout)
    payload = {
        "touser": touser,
        "msgtype": "markdown",
        "agentid": agentid,
        "markdown": {"content": content[:4000]},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = f"{SEND_URL}?access_token={token}"
    req = request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errcode") != 0:
        raise RuntimeError(
            f"WeCom send failed: errcode={result.get('errcode')} errmsg={result.get('errmsg')} "
            f"invaliduser={result.get('invaliduser')}"
        )
    return result
