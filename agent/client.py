import json
from typing import Any
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
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.timeout_s = timeout_s
        self._client = httpx.Client(
            base_url=self.base_url,
            transport=self.transport,
            timeout=self.timeout_s,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

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
        if tools is not None:
            payload["tools"] = tools

        try:
            resp = self._client.post("/chat/completions", json=payload)
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

        if "choices" not in data:
            raise ClientError("Response missing 'choices'")

        return data

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
