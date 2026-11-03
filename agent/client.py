import json
import time
from typing import Any, Callable
import httpx


class ClientError(Exception):
    """Raised when an OpenRouter API request fails or returns an error."""


def _extract_error_message(data: Any) -> str | None:
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        if isinstance(err, dict):
            return str(err.get("message") or err)
        return str(err)
    return None


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 120.0,
        max_retries: int = 3,
        backoff_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        max_tokens: int | None = 4096,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.sleep = sleep
        self.max_tokens = max_tokens
        self._client = httpx.Client(
            base_url=self.base_url,
            transport=self.transport,
            timeout=self.timeout_s,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    def _post(self, payload: dict) -> httpx.Response:
        resp: httpx.Response | None = None
        for attempt in range(max(0, self.max_retries) + 1):
            try:
                resp = self._client.post("/chat/completions", json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < self.max_retries:
                    self.sleep(self.backoff_s * (2 ** attempt))
                    continue
                raise ClientError(f"HTTP request failed: {exc}") from exc
            except httpx.HTTPError as exc:
                raise ClientError(f"HTTP request failed: {exc}") from exc

            if resp.status_code == 429 or (500 <= resp.status_code < 600):
                if attempt < self.max_retries:
                    self.sleep(self.backoff_s * (2 ** attempt))
                    continue

            break

        if resp is None:
            raise ClientError("HTTP request failed: no response")

        return resp

    def _parse(self, resp: httpx.Response) -> dict:
        if resp.is_error:
            try:
                err_data = resp.json()
                msg = _extract_error_message(err_data)
                if msg:
                    raise ClientError(msg)
            except (json.JSONDecodeError, ValueError):
                pass
            raise ClientError(f"HTTP error {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ClientError(f"Invalid JSON response: {exc}") from exc

        if not isinstance(data, dict):
            raise ClientError(f"Response must be a dict: {data}")

        msg = _extract_error_message(data)
        if msg:
            raise ClientError(msg)

        if not isinstance(data.get("choices"), list) or not data["choices"]:
            raise ClientError("Response missing or empty 'choices'")

        return data

    def chat(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "usage": {"include": True},
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if tools is not None:
            payload["tools"] = tools

        for attempt in range(max(0, self.max_retries) + 1):
            data = self._parse(self._post(payload))
            if data["choices"][0].get("finish_reason") != "error":
                return data
            if attempt < self.max_retries:
                self.sleep(self.backoff_s * (2 ** attempt))

        raise ClientError("provedor devolveu finish_reason error")

    def models(self) -> list[dict]:
        try:
            resp = self._client.get("/models")
        except httpx.HTTPError as exc:
            raise ClientError(f"HTTP request failed: {exc}") from exc

        if resp.is_error:
            try:
                err_data = resp.json()
                msg = _extract_error_message(err_data)
                if msg:
                    raise ClientError(msg)
            except (json.JSONDecodeError, ValueError):
                pass
            raise ClientError(f"HTTP error {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ClientError(f"Invalid JSON response: {exc}") from exc

        if not isinstance(data, dict):
            raise ClientError(f"Response must be a dict: {data}")

        msg = _extract_error_message(data)
        if msg:
            raise ClientError(msg)

        if "data" not in data or not isinstance(data["data"], list):
            raise ClientError("Response missing 'data' list")

        return data["data"]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OpenRouterClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
