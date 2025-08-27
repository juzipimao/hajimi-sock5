import json
import os
from app.models.schemas import ChatCompletionRequest
from dataclasses import dataclass
from typing import Optional
import httpx
import secrets
import string
import app.config.settings as settings

from app.utils.logging import log


def generate_secure_random_string(length):
    all_characters = string.ascii_letters + string.digits
    secure_random_string = "".join(
        secrets.choice(all_characters) for _ in range(length)
    )
    return secure_random_string


@dataclass
class GeneratedText:
    text: str
    finish_reason: Optional[str] = None


class OpenAIClient:
    AVAILABLE_MODELS = []
    EXTRA_MODELS = os.environ.get("EXTRA_MODELS", "").split(",")

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _build_socks5_proxy_url(self) -> str | None:
        if not settings.PROXY_SOCKS5_ENABLED:
            return None
        host = (settings.PROXY_SOCKS5_HOST or '').strip()
        port = int(settings.PROXY_SOCKS5_PORT or 0)
        if not host or port <= 0:
            return None
        user = (settings.PROXY_SOCKS5_USERNAME or '').strip()
        pwd = (settings.PROXY_SOCKS5_PASSWORD or '')
        if user and pwd:
            auth = f"{user}:{pwd}@"
        elif user and not pwd:
            auth = f"{user}:@"
        else:
            auth = ""
        return f"socks5h://{auth}{host}:{port}"

    def _create_async_client(self):
        proxy_url = self._build_socks5_proxy_url()
        def _mask(url: str) -> str:
            try:
                if '://' in url and '@' in url:
                    scheme, rest = url.split('://', 1)
                    cred_host = rest.split('@', 1)
                    if len(cred_host) == 2:
                        userpass, hostpart = cred_host
                        user = userpass.split(':', 1)[0]
                        return f"{scheme}://{user}:******@{hostpart}"
            except Exception:
                pass
            return url

        if proxy_url:
            try:
                client = httpx.AsyncClient(proxies={"all": proxy_url}, trust_env=False)
                meta = {"proxy_enabled": True, "proxy_mode": "proxies_param", "proxy_url_masked": _mask(proxy_url)}
                return client, meta
            except TypeError:
                old_all = os.environ.get("ALL_PROXY")
                os.environ["ALL_PROXY"] = proxy_url
                client = httpx.AsyncClient(trust_env=True)
                meta = {"proxy_enabled": True, "proxy_mode": "env_fallback", "proxy_url_masked": _mask(proxy_url), "_old_all_proxy": old_all}
                return client, meta
        client = httpx.AsyncClient(trust_env=False)
        meta = {"proxy_enabled": False, "proxy_mode": "disabled"}
        return client, meta

    def filter_data_by_whitelist(data, allowed_keys):
        """
        根据白名单过滤字典。
        Args:
            data (dict): 原始的 Python 字典 (代表 JSON 对象)。
            allowed_keys (list or set): 包含允许保留的键名的列表或集合。
                                        使用集合 (set) 进行查找通常更快。
        Returns:
            dict: 只包含白名单中键的新字典。
        """
        # 使用集合(set)可以提高查找效率，特别是当白名单很大时
        allowed_keys_set = set(allowed_keys)
        # 使用字典推导式创建过滤后的新字典
        filtered_data = {
            key: value for key, value in data.items() if key in allowed_keys_set
        }
        return filtered_data

    # 真流式处理
    async def stream_chat(self, request: ChatCompletionRequest):
        whitelist = [
            "model",
            "messages",
            "temperature",
            "max_tokens",
            "stream",
            "tools",
            "reasoning_effort",
            "top_k",
            "presence_penalty",
        ]

        data = self.filter_data_by_whitelist(request, whitelist)

        if settings.search["search_mode"] and data.model.endswith("-search"):
            log(
                "INFO",
                "开启联网搜索模式",
                extra={"key": self.api_key[:8], "model": request.model},
            )
            data.setdefault("tools", []).append({"google_search": {}})

        data.model = data.model.removesuffix("-search")

        # 真流式请求处理逻辑
        extra_log = {
            "key": self.api_key[:8],
            "request_type": "stream",
            "model": request.model,
        }
        log("INFO", "流式请求开始", extra=extra_log)

        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        client, meta = self._create_async_client()
        log("info", "准备发起OpenAI兼容流式请求", extra={"request_url": url, **meta})
        try:
            async with client as client:
                async with client.stream(
                    "POST", url, headers=headers, json=data, timeout=600
                ) as response:
                 buffer = b""  # 用于累积可能不完整的 JSON 数据
                try:
                    async for line in response.aiter_lines():
                        if not line.strip():  # 跳过空行 (SSE 消息分隔符)
                            continue
                        if line.startswith("data: "):
                            line = line[len("data: ") :].strip()  # 去除 "data: " 前缀

                        # 检查是否是结束标志，如果是，结束循环
                        if line == "[DONE]":
                            break

                        buffer += line.encode("utf-8")
                        try:
                            # 尝试解析整个缓冲区
                            data = json.loads(buffer.decode("utf-8"))
                            # 解析成功，清空缓冲区
                            buffer = b""

                            yield data

                        except json.JSONDecodeError:
                            # JSON 不完整，继续累积到 buffer
                            continue
                        except Exception as e:
                            log(
                                "ERROR",
                                "流式处理期间发生错误",
                                extra={
                                    "key": self.api_key[:8],
                                    "request_type": "stream",
                                    "model": request.model,
                                },
                            )
                            raise e
                except Exception as e:
                    raise e
                finally:
                    log("info", "流式请求结束")
        finally:
            if meta.get("proxy_mode") == "env_fallback":
                old = meta.get("_old_all_proxy")
                if old is None:
                    os.environ.pop("ALL_PROXY", None)
                else:
                    os.environ["ALL_PROXY"] = old
