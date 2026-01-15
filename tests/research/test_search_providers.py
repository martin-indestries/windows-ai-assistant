"""Tests for search providers."""

from unittest.mock import Mock, patch

import pytest  # noqa: F401

from spectral.research.search_providers import (
    DuckDuckGoHtmlProvider,
    SearchProviderChain,
)


@pytest.fixture
def mock_ddg_html_response():
    """Mock DuckDuckGo HTML response."""
    return """
    <html>
        <body>
            <div class="result">
                <a class="result__a" href="https://example.com/1">Example Result 1</a>
                <a class="result__snippet">This is the first result snippet</a>
            </div>
            <div class="result">
                <a class="result__a" href="https://example.com/2">Example Result 2</a>
                <a class="result__snippet">This is the second result snippet</a>
            </div>
        </body>
    </html>
    """


def test_ddg_html_provider_parsing(mock_ddg_html_response):
    """Test DuckDuckGo HTML provider result parsing."""
    provider = DuckDuckGoHtmlProvider()

    with patch("requests.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_ddg_html_response
        mock_post.return_value = mock_response

        results = provider.search("test query", max_results=5)

        assert len(results) == 2
        assert results[0].title == "Example Result 1"
        assert results[0].url == "https://example.com/1"
        assert "first result" in results[0].snippet


def test_ddg_html_provider_blocked():
    """Test DuckDuckGo HTML provider handles 403 response."""
    provider = DuckDuckGoHtmlProvider()

    with patch("requests.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        results = provider.search("test query")

        assert len(results) == 0


def test_ddg_html_provider_timeout():
    """Test DuckDuckGo HTML provider handles timeout."""
    provider = DuckDuckGoHtmlProvider()

    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("Timeout")

        results = provider.search("test query")

        assert len(results) == 0


def test_search_provider_chain_fallback():
    """Test search provider chain fallback mechanism."""
    chain = SearchProviderChain()

    with patch.object(chain.providers[0], "search", return_value=[]):
        with patch.object(chain.providers[1], "search") as mock_fallback:
            mock_fallback.return_value = [
                Mock(title="Result", url="https://example.com", snippet="Snippet", rank=1)
            ]

            results = chain.search("test query")

            assert len(results) == 1
            mock_fallback.assert_called_once()


def test_rate_limiting():
    """Test rate limiting delays requests."""
    provider = DuckDuckGoHtmlProvider()

    import time

    start = time.time()
    provider.rate_limit("test.com")
    provider.rate_limit("test.com")
    elapsed = time.time() - start

    assert elapsed >= provider.cooldown_seconds
