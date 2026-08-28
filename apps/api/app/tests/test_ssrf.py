"""The research fetcher must block internal/private/metadata targets (§43)."""
import pytest

from app.research.fetcher import SSRFBlockedError, _validate_url, safe_fetch_binary


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP/Azure metadata
        "http://100.100.100.200/",  # Alibaba Cloud metadata
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://[::1]/",
        "ftp://example.com/",
        "file:///etc/passwd",
        "http://0.0.0.0/",
    ],
)
def test_blocked_targets_are_rejected(url):
    with pytest.raises(SSRFBlockedError):
        _validate_url(url)


@pytest.mark.parametrize("url", ["http://example.com/", "https://www.wikipedia.org/"])
def test_public_targets_pass_validation(url):
    _validate_url(url)  # should not raise


def test_blocked_port_is_rejected():
    with pytest.raises(SSRFBlockedError):
        _validate_url("http://example.com:6379/")


def test_safe_fetch_binary_applies_the_same_ssrf_validation():
    """safe_fetch_binary (used to download product-screenshot/search-
    sourced images) must go through the same _validate_url check as
    safe_fetch, not a separate/weaker path."""
    with pytest.raises(SSRFBlockedError):
        safe_fetch_binary("http://169.254.169.254/latest/meta-data/")
