"""Firecrawl-based crawler for extracting API docs and site structure."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from firecrawl import FirecrawlApp


@dataclass
class CrawlResult:
    """Result from crawling a site."""
    url: str
    title: str = ""
    markdown: str = ""
    html: str = ""
    metadata: dict = field(default_factory=dict)
    links: list[str] = field(default_factory=list)


class FirecrawlCrawler:
    """Use Firecrawl to extract API documentation and site structure."""

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if api_url:
            kwargs["api_url"] = api_url
        self.app = FirecrawlApp(**kwargs)

    def scrape_url(self, url: str, formats: list[str] | None = None) -> CrawlResult:
        """Scrape a single URL and return structured content."""
        formats = formats or ["markdown", "html"]
        result = self.app.scrape_url(url, formats=formats)

        return CrawlResult(
            url=url,
            title=getattr(result, "metadata", {}).get("title", "") if hasattr(result, "metadata") else "",
            markdown=getattr(result, "markdown", "") or "",
            html=getattr(result, "html", "") or "",
            metadata=getattr(result, "metadata", {}) or {},
            links=getattr(result, "links", []) or [],
        )

    def discover_api_docs(self, base_url: str, max_pages: int = 20) -> list[CrawlResult]:
        """
        Crawl a site looking for API documentation pages.
        Returns pages most likely to contain API endpoint definitions.
        """
        # Common API doc URL patterns
        api_patterns = [
            "/api", "/docs", "/reference", "/swagger", "/openapi",
            "/api-docs", "/v1", "/v2", "/developers",
        ]

        params = {
            "limit": max_pages,
            "scrapeOptions": {"formats": ["markdown"]},
            "includePaths": api_patterns,
        }

        crawl_result = self.app.crawl_url(base_url, params=params)
        results = []

        if hasattr(crawl_result, "data"):
            pages = crawl_result.data
        elif isinstance(crawl_result, list):
            pages = crawl_result
        else:
            pages = [crawl_result]

        for page in pages:
            md = getattr(page, "markdown", "") or ""
            metadata = getattr(page, "metadata", {}) or {}
            url = metadata.get("sourceURL", getattr(page, "url", base_url))
            results.append(CrawlResult(
                url=url,
                title=metadata.get("title", ""),
                markdown=md,
                metadata=metadata,
            ))

        return results

    def extract_openapi_specs(self, base_url: str) -> list[str]:
        """
        Try to find OpenAPI/Swagger spec URLs on a site.
        Returns list of discovered spec URLs.
        """
        common_paths = [
            "/openapi.json", "/swagger.json", "/api-docs",
            "/swagger/v1/swagger.json", "/v1/openapi.json",
            "/v2/api-docs", "/api/openapi.json",
            "/.well-known/openapi.json",
            "/docs/openapi.json",
        ]

        import httpx
        found = []
        client = httpx.Client(follow_redirects=True, timeout=10)

        for path in common_paths:
            url = base_url.rstrip("/") + path
            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct or "yaml" in ct:
                        # Validate it's actually an OpenAPI spec
                        try:
                            data = resp.json()
                            if "openapi" in data or "swagger" in data or "paths" in data:
                                found.append(url)
                        except Exception:
                            if "openapi:" in resp.text or "swagger:" in resp.text:
                                found.append(url)
            except Exception:
                continue

        client.close()
        return found

    def extract_api_from_docs(self, crawl_results: list[CrawlResult]) -> dict:
        """
        Analyze crawled documentation pages and extract API structure.
        Returns a structured summary of discovered endpoints.
        """
        endpoints = []
        base_patterns = set()

        for result in crawl_results:
            text = result.markdown
            # Look for API endpoint patterns in docs
            import re

            # HTTP method + path patterns
            pattern = r'(GET|POST|PUT|PATCH|DELETE|HEAD)\s+([/\w{}.:]+)'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for method, path in matches:
                endpoints.append({"method": method.upper(), "path": path, "source": result.url})

            # URL patterns that look like API endpoints
            url_pattern = r'(?:https?://[^\s)]+)?(/api/v?\d*/[^\s\)"\']+|/v\d+/[^\s\)"\']+)'
            url_matches = re.findall(url_pattern, text)
            for path in url_matches:
                base_patterns.add(path.split("{")[0].rstrip("/"))

        return {
            "endpoints": endpoints,
            "base_patterns": sorted(base_patterns),
            "pages_analyzed": len(crawl_results),
        }
