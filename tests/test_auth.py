"""
Unit tests for auth classes.

Integration tests also exist in tests/client/test_auth.py
"""

from urllib.request import parse_keqv_list

import pytest

import httpx


def test_basic_auth():
    auth = httpx.BasicAuth(username="user", password="pass")
    request = httpx.Request("GET", "https://www.example.com")

    # The initial request should include a basic auth header.
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert request.headers["Authorization"].startswith("Basic")

    # No other requests are made.
    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopIteration):
        flow.send(response)


def test_digest_auth_with_200():
    auth = httpx.DigestAuth(username="user", password="pass")
    request = httpx.Request("GET", "https://www.example.com")

    # The initial request should not include an auth header.
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert "Authorization" not in request.headers

    # If a 200 response is returned, then no other requests are made.
    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopIteration):
        flow.send(response)


def test_digest_auth_with_401():
    auth = httpx.DigestAuth(username="user", password="pass")
    request = httpx.Request("GET", "https://www.example.com")

    # The initial request should not include an auth header.
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert "Authorization" not in request.headers

    # If a 401 response is returned, then a digest auth request is made.
    headers = {
        "WWW-Authenticate": 'Digest realm="...", qop="auth", nonce="...", opaque="..."'
    }
    response = httpx.Response(
        content=b"Auth required", status_code=401, headers=headers, request=request
    )
    request = flow.send(response)
    assert request.headers["Authorization"].startswith("Digest")

    # No other requests are made.
    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopIteration):
        flow.send(response)


def test_digest_auth_with_401_nonce_counting():
    auth = httpx.DigestAuth(username="user", password="pass")
    request = httpx.Request("GET", "https://www.example.com")

    # The initial request should not include an auth header.
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert "Authorization" not in request.headers

    # If a 401 response is returned, then a digest auth request is made.
    headers = {
        "WWW-Authenticate": 'Digest realm="...", qop="auth", nonce="...", opaque="..."'
    }
    response = httpx.Response(
        content=b"Auth required", status_code=401, headers=headers, request=request
    )
    first_request = flow.send(response)
    assert first_request.headers["Authorization"].startswith("Digest")

    # Each subsequent request contains the digest header by default...
    request = httpx.Request("GET", "https://www.example.com")
    flow = auth.sync_auth_flow(request)
    second_request = next(flow)
    assert second_request.headers["Authorization"].startswith("Digest")

    # ... and the client nonce count (nc) is increased
    first_nc = parse_keqv_list(first_request.headers["Authorization"].split(", "))["nc"]
    second_nc = parse_keqv_list(second_request.headers["Authorization"].split(", "))[
        "nc"
    ]
    assert int(first_nc, 16) + 1 == int(second_nc, 16)

    # No other requests are made.
    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopIteration):
        flow.send(response)


def set_cookies(request: httpx.Request) -> httpx.Response:
    headers = {
        "Set-Cookie": "session=.session_value...",
        "WWW-Authenticate": 'Digest realm="...", qop="auth", nonce="...", opaque="..."',
    }
    if request.url.path == "/auth":
        return httpx.Response(
            content=b"Auth required", status_code=401, headers=headers
        )
    else:
        raise NotImplementedError()  # pragma: no cover


def test_digest_auth_setting_cookie_in_request():
    url = "https://www.example.com/auth"
    client = httpx.Client(transport=httpx.MockTransport(set_cookies))
    request = client.build_request("GET", url)

    auth = httpx.DigestAuth(username="user", password="pass")
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert "Authorization" not in request.headers

    response = client.get(url)
    assert len(response.cookies) > 0
    assert response.cookies["session"] == ".session_value..."

    request = flow.send(response)
    assert request.headers["Authorization"].startswith("Digest")
    assert request.headers["Cookie"] == "session=.session_value..."

    # No other requests are made.
    response = httpx.Response(
        content=b"Hello, world!", status_code=200, request=request
    )
    with pytest.raises(StopIteration):
        flow.send(response)


def test_digest_auth_rfc_2069():
    # Example from https://datatracker.ietf.org/doc/html/rfc2069#section-2.4
    # with corrected response from https://www.rfc-editor.org/errata/eid749

    auth = httpx.DigestAuth(username="Mufasa", password="CircleOfLife")
    request = httpx.Request("GET", "https://www.example.com/dir/index.html")

    # The initial request should not include an auth header.
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert "Authorization" not in request.headers

    # If a 401 response is returned, then a digest auth request is made.
    headers = {
        "WWW-Authenticate": (
            'Digest realm="testrealm@host.com", '
            'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", '
            'opaque="5ccc069c403ebaf9f0171e9517f40e41"'
        )
    }
    response = httpx.Response(
        content=b"Auth required", status_code=401, headers=headers, request=request
    )
    request = flow.send(response)
    assert request.headers["Authorization"].startswith("Digest")
    assert 'username="Mufasa"' in request.headers["Authorization"]
    assert 'realm="testrealm@host.com"' in request.headers["Authorization"]
    assert (
        'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093"' in request.headers["Authorization"]
    )
    assert 'uri="/dir/index.html"' in request.headers["Authorization"]
    assert (
        'opaque="5ccc069c403ebaf9f0171e9517f40e41"' in request.headers["Authorization"]
    )
    assert (
        'response="1949323746fe6a43ef61f9606e7febea"'
        in request.headers["Authorization"]
    )

    # No other requests are made.
    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopIteration):
        flow.send(response)


def test_digest_auth_rfc_7616_md5(monkeypatch):
    # Example from https://datatracker.ietf.org/doc/html/rfc7616#section-3.9.1

    def mock_get_client_nonce(nonce_count: int, nonce: bytes) -> bytes:
        return "f2/wE4q74E6zIJEtWaHKaf5wv/H5QzzpXusqGemxURZJ".encode()

    auth = httpx.DigestAuth(username="Mufasa", password="Circle of Life")
    monkeypatch.setattr(auth, "_get_client_nonce", mock_get_client_nonce)

    request = httpx.Request("GET", "https://www.example.com/dir/index.html")

    # The initial request should not include an auth header.
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert "Authorization" not in request.headers

    # If a 401 response is returned, then a digest auth request is made.
    headers = {
        "WWW-Authenticate": (
            'Digest realm="http-auth@example.org", '
            'qop="auth, auth-int", '
            "algorithm=MD5, "
            'nonce="7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v", '
            'opaque="FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS"'
        )
    }
    response = httpx.Response(
        content=b"Auth required", status_code=401, headers=headers, request=request
    )
    request = flow.send(response)
    assert request.headers["Authorization"].startswith("Digest")
    assert 'username="Mufasa"' in request.headers["Authorization"]
    assert 'realm="http-auth@example.org"' in request.headers["Authorization"]
    assert 'uri="/dir/index.html"' in request.headers["Authorization"]
    assert "algorithm=MD5" in request.headers["Authorization"]
    assert (
        'nonce="7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v"'
        in request.headers["Authorization"]
    )
    assert "nc=00000001" in request.headers["Authorization"]
    assert (
        'cnonce="f2/wE4q74E6zIJEtWaHKaf5wv/H5QzzpXusqGemxURZJ"'
        in request.headers["Authorization"]
    )
    assert "qop=auth" in request.headers["Authorization"]
    assert (
        'opaque="FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS"'
        in request.headers["Authorization"]
    )
    assert (
        'response="8ca523f5e9506fed4657c9700eebdbec"'
        in request.headers["Authorization"]
    )

    # No other requests are made.
    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopIteration):
        flow.send(response)


def test_digest_auth_rfc_7616_sha_256(monkeypatch):
    # Example from https://datatracker.ietf.org/doc/html/rfc7616#section-3.9.1

    def mock_get_client_nonce(nonce_count: int, nonce: bytes) -> bytes:
        return "f2/wE4q74E6zIJEtWaHKaf5wv/H5QzzpXusqGemxURZJ".encode()

    auth = httpx.DigestAuth(username="Mufasa", password="Circle of Life")
    monkeypatch.setattr(auth, "_get_client_nonce", mock_get_client_nonce)

    request = httpx.Request("GET", "https://www.example.com/dir/index.html")

    # The initial request should not include an auth header.
    flow = auth.sync_auth_flow(request)
    request = next(flow)
    assert "Authorization" not in request.headers

    # If a 401 response is returned, then a digest auth request is made.
    headers = {
        "WWW-Authenticate": (
            'Digest realm="http-auth@example.org", '
            'qop="auth, auth-int", '
            "algorithm=SHA-256, "
            'nonce="7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v", '
            'opaque="FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS"'
        )
    }
    response = httpx.Response(
        content=b"Auth required", status_code=401, headers=headers, request=request
    )
    request = flow.send(response)
    assert request.headers["Authorization"].startswith("Digest")
    assert 'username="Mufasa"' in request.headers["Authorization"]
    assert 'realm="http-auth@example.org"' in request.headers["Authorization"]
    assert 'uri="/dir/index.html"' in request.headers["Authorization"]
    assert "algorithm=SHA-256" in request.headers["Authorization"]
    assert (
        'nonce="7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v"'
        in request.headers["Authorization"]
    )
    assert "nc=00000001" in request.headers["Authorization"]
    assert (
        'cnonce="f2/wE4q74E6zIJEtWaHKaf5wv/H5QzzpXusqGemxURZJ"'
        in request.headers["Authorization"]
    )
    assert "qop=auth" in request.headers["Authorization"]
    assert (
        'opaque="FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS"'
        in request.headers["Authorization"]
    )
    assert (
        'response="753927fa0e85d155564e2e272a28d1802ca10daf4496794697cf8db5856cb6c1"'
        in request.headers["Authorization"]
    )

    # No other requests are made.
    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopIteration):
        flow.send(response)


@pytest.mark.anyio
async def test_digest_auth_with_401_async():
    auth = httpx.DigestAuth(username="user", password="pass")
    request = httpx.Request("GET", "https://www.example.com")

    flow = auth.async_auth_flow(request)
    request = await flow.__anext__()
    assert "Authorization" not in request.headers

    headers = {
        "WWW-Authenticate": 'Digest realm="...", qop="auth", nonce="...", opaque="..."'
    }
    response = httpx.Response(
        content=b"Auth required", status_code=401, headers=headers, request=request
    )
    request = await flow.asend(response)
    assert request.headers["Authorization"].startswith("Digest")

    response = httpx.Response(content=b"Hello, world!", status_code=200)
    with pytest.raises(StopAsyncIteration):
        await flow.asend(response)


@pytest.mark.anyio
async def test_digest_auth_sync_async_parity(monkeypatch):
    def mock_get_client_nonce(nonce_count: int, nonce: bytes) -> bytes:
        return b"fixed_cnonce_val"

    auth = httpx.DigestAuth(username="user", password="pass")
    monkeypatch.setattr(auth, "_get_client_nonce", mock_get_client_nonce)

    headers_401 = {
        "WWW-Authenticate": 'Digest realm="...", qop="auth", nonce="...", opaque="..."'
    }

    # Drive sync_auth_flow
    request_sync = httpx.Request("GET", "https://www.example.com")
    sync_flow = auth.sync_auth_flow(request_sync)
    request_sync = next(sync_flow)
    response_401 = httpx.Response(
        content=b"Auth required",
        status_code=401,
        headers=headers_401,
        request=request_sync,
    )
    request_sync = sync_flow.send(response_401)
    sync_auth_header = request_sync.headers["Authorization"]
    response_200 = httpx.Response(content=b"OK", status_code=200)
    with pytest.raises(StopIteration):
        sync_flow.send(response_200)

    # Reset state for async path
    auth._last_challenge = None
    auth._nonce_count = 1

    # Drive async_auth_flow
    request_async = httpx.Request("GET", "https://www.example.com")
    async_flow = auth.async_auth_flow(request_async)
    request_async = await async_flow.__anext__()
    response_401 = httpx.Response(
        content=b"Auth required",
        status_code=401,
        headers=headers_401,
        request=request_async,
    )
    request_async = await async_flow.asend(response_401)
    async_auth_header = request_async.headers["Authorization"]
    response_200 = httpx.Response(content=b"OK", status_code=200)
    with pytest.raises(StopAsyncIteration):
        await async_flow.asend(response_200)

    assert sync_auth_header == async_auth_header
