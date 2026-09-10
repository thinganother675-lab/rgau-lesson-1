"""Bounded, sequential HTTP with cache timestamps and safe diagnostics."""

import hashlib
import json
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .providers.base import ProviderError


class Http:
    def __init__(
        self,
        cache="data/cache",
        *,
        offline=False,
        ttl=86400,
        client=None,
        sleep=time.sleep,
        min_interval=1.05,
    ):
        self.cache = Path(cache)
        self.offline, self.ttl = offline, ttl
        self.client = client or httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "sciagg-ru/0.1 (academic metadata prototype)"},
        )
        self.sleep, self.min_interval = sleep, min_interval
        self.last_request = {}
        self.host_interval = {}
        self.last_retrieved_at = ""
        self.cache_hit = False

    def close(self):
        self.client.close()

    def get(self, source, url, *, params=None, headers=None):
        # Auth influences hash to prevent using one entitlement's cache for another.
        # No token appears in the stored key, filename, URL, metadata or diagnostics.
        key = hashlib.sha256(
            json.dumps([url, params or {}, headers or {}], sort_keys=True).encode()
        ).hexdigest()
        path = self.cache / f"{key}.json"
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if self.offline or time.time() - saved["saved_at"] < self.ttl:
                    self.last_retrieved_at = saved["retrieved_at"]
                    self.cache_hit = True
                    return saved["data"]
            except (ValueError, KeyError):
                pass
        if self.offline:
            raise ProviderError(source, "offline: отсутствует сохранённый ответ")
        host = urlsplit(url).netloc
        for attempt in range(3):
            wait = max(self.min_interval, self.host_interval.get(host, 0)) - (
                time.monotonic() - self.last_request.get(host, 0)
            )
            if wait > 0:
                self.sleep(wait)
            self.last_request[host] = time.monotonic()
            try:
                response = self.client.get(url, params=params, headers=headers)
            except httpx.RequestError:
                if attempt == 2:
                    raise ProviderError(source, "сетевая ошибка/тайм-аут") from None
                self.sleep(2**attempt + random.random() / 4)
                continue
            if response.status_code in (429, 500, 502, 503, 504):
                retry = response.headers.get("Retry-After", "")
                try:
                    delay = float(retry)
                except ValueError:
                    try:
                        delay = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError):
                        delay = 2**attempt + random.random() / 4
                reset = response.headers.get("X-RateLimit-Reset")
                if response.status_code == 429 and reset:
                    try:
                        # Elsevier reset is Unix time; OpenAlex documents seconds until UTC reset.
                        quota_delay = float(reset)
                        if quota_delay > 1_000_000_000:
                            quota_delay -= time.time()
                        delay = max(delay, quota_delay)
                    except ValueError:
                        pass
                # Long quota resets are reported; never retry earlier than instructed.
                if attempt == 2 or delay > 30:
                    raise ProviderError(
                        source, "лимит/временная недоступность; повторите позже", response.status_code
                    )
                self.sleep(max(0, delay))
                continue
            if not response.is_success:
                raise ProviderError(source, "запрос отклонён источником", response.status_code)
            try:
                data = response.json()
            except ValueError:
                raise ProviderError(source, "ожидался JSON, формат источника изменился") from None
            stamp = datetime.now(timezone.utc).isoformat()
            if source == "crossref":
                try:
                    rate = float(response.headers["x-rate-limit-limit"])
                    interval = float(response.headers["x-rate-limit-interval"].removesuffix("s"))
                    if rate > 0 and interval > 0:
                        self.host_interval[host] = interval / rate + 0.05
                except (KeyError, ValueError):
                    pass
            self.cache.mkdir(parents=True, exist_ok=True)
            parts = urlsplit(url)
            endpoint = f"{parts.scheme}://{parts.hostname}{parts.path}"
            payload = {
                "saved_at": time.time(),
                "retrieved_at": stamp,
                "source": source,
                "endpoint": endpoint,
                "data": data,
            }
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temp.replace(path)
            self.last_retrieved_at, self.cache_hit = stamp, False
            return data
        raise ProviderError(source, "исчерпаны повторы")
