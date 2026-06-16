# agents/scout.py
import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any, cast

import feedparser  # type: ignore[import-untyped]
import httpx
from loguru import logger
from redis.asyncio import Redis

from agents.state import RawNewsItem
from api.config import settings

# Construct standard Redis URL using configuration
REDIS_URL = f"redis://{settings.POSTGRES_HOST}:{settings.REDIS_PORT}/0"
redis_client: Redis = Redis.from_url(REDIS_URL, decode_responses=True)  # type: ignore[reportUnknownMemberType]


class RedisDeduplicator:
    def __init__(self, client: Redis):
        self.client = client
        self.ttl = 86400  # 24 hours in seconds

    async def is_new(self, url: str, tenant_id: str) -> bool:
        """
        Validates URL uniqueness using atomic Redis SET NX.
        Strictly isolates deduplication per tenant.
        Returns True if the URL was inserted (is new), False if it already exists.
        """
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

        # Enforce tenant isolation in cache keys
        key = f"news:dedup:{tenant_id}:{url_hash}"

        # Atomic SET with Not eXists condition to prevent race conditions
        result = await self.client.set(key, "1", nx=True, ex=self.ttl)
        return bool(result)


class ScoutAgent:
    def __init__(self):
        self.deduplicator = RedisDeduplicator(redis_client)
        self.http_timeout = 5.0

    async def _fetch_hacker_news(self, topic: str, tenant_id: str) -> list[RawNewsItem]:
        results: list[RawNewsItem] = []
        try:
            url = "https://hn.algolia.com/api/v1/search"
            params = {"tags": "story", "query": topic, "hitsPerPage": 5}

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = cast(dict[str, Any], response.json())

            hits = cast(list[dict[str, Any]], data.get("hits", []))
            for hit in hits:
                item_url = str(hit.get("url") or hit.get("story_url") or "")
                if not item_url:
                    continue

                if await self.deduplicator.is_new(item_url, tenant_id):
                    results.append(
                        RawNewsItem(
                            title=hit.get("title", "No Title"),
                            text=hit.get("story_text") or hit.get("title", ""),
                            source="HackerNews",
                            url=item_url,
                            published_at=datetime.now(UTC),
                            relevance_score=0.8,
                        )
                    )
        except Exception as e:
            # Structured JSON logging for Fault Tolerance
            logger.error(
                {
                    "event": "scout_fetch_error",
                    "source": "HackerNews",
                    "topic": topic,
                    "tenant_id": tenant_id,
                    "error": str(e),
                }
            )
        return results

    async def _fetch_rss_feed(
        self, feed_url: str, source_name: str, topic: str, tenant_id: str
    ) -> list[RawNewsItem]:
        results: list[RawNewsItem] = []
        try:
            # Explicitly type dynamic feedparser results and suppress untyped module errors
            feed: Any = await asyncio.to_thread(feedparser.parse, feed_url)  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            entries: list[Any] = getattr(feed, "entries", [])

            for entry in entries[:5]:
                item_url = str(getattr(entry, "link", ""))
                if not item_url:
                    continue

                title = str(getattr(entry, "title", ""))
                summary = str(getattr(entry, "summary", ""))

                # Basic context filtering
                if (
                    topic.lower() not in title.lower()
                    and topic.lower() not in summary.lower()
                ):
                    continue

                if await self.deduplicator.is_new(item_url, tenant_id):
                    results.append(
                        RawNewsItem(
                            title=title,
                            text=summary,
                            source=source_name,
                            url=item_url,
                            published_at=datetime.now(UTC),
                            relevance_score=0.7,
                        )
                    )
        except Exception as e:
            # Structured JSON logging
            logger.error(
                {
                    "event": "scout_fetch_error",
                    "source": source_name,
                    "feed_url": feed_url,
                    "topic": topic,
                    "tenant_id": tenant_id,
                    "error": str(e),
                }
            )
        return results

    async def gather_news(self, topic: str, tenant_id: str) -> list[RawNewsItem]:
        """
        Executes parallel fetching from all registered sources.
        Fault-tolerant: a failure in one source won't stop the others.
        """
        tasks = [
            self._fetch_hacker_news(topic, tenant_id),
            self._fetch_rss_feed(
                "https://techcrunch.com/feed/", "TechCrunch", topic, tenant_id
            ),
            self._fetch_rss_feed(
                "https://www.wired.com/feed/rss", "Wired", topic, tenant_id
            ),
        ]

        # asyncio.gather will safely complete because inner methods catch exceptions
        results_nested = await asyncio.gather(*tasks)

        # Flatten the list of lists
        flattened = [item for sublist in results_nested for item in sublist]

        logger.info(
            {
                "event": "scout_gathering_complete",
                "topic": topic,
                "tenant_id": tenant_id,
                "items_found": len(flattened),
            }
        )

        return flattened


if __name__ == "__main__":
    import sys

    # CLI Test Execution for gather_news and Redis deduplication
    async def run_test() -> None:
        logger.configure(
            handlers=[{"sink": sys.stdout, "format": "{message}", "serialize": True}]
        )
        agent = ScoutAgent()
        test_tenant = "00000000-0000-0000-0000-000000000001"
        test_topic = "AI"

        print(f"Scouting '{test_topic}' (Run 1)...")
        news = await agent.gather_news(test_topic, test_tenant)
        print(f"Found {len(news)} items.")
        for item in news:
            print(f"- {item.source}: {item.title}")

        print(f"\nScouting '{test_topic}' (Run 2 - Deduplication check)...")
        news_dup = await agent.gather_news(test_topic, test_tenant)
        print(f"Found {len(news_dup)} items (Expected 0 due to nx=True).")

    asyncio.run(run_test())
