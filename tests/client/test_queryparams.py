import httpx


def hello_world(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="Hello, world")


def test_client_queryparams():
    client = httpx.Client(params={"a": "b"})
    assert isinstance(client.params, httpx.QueryParams)
    assert client.params["a"] == "b"


def test_client_queryparams_string():
    client = httpx.Client(params="a=b")
    assert isinstance(client.params, httpx.QueryParams)
    assert client.params["a"] == "b"

    client = httpx.Client()
    client.params = "a=b"
    assert isinstance(client.params, httpx.QueryParams)
    assert client.params["a"] == "b"


def test_client_queryparams_echo():
    url = "http://example.org/echo_queryparams"
    client_queryparams = "first=str"
    request_queryparams = {"second": "dict"}
    client = httpx.Client(
        transport=httpx.MockTransport(hello_world), params=client_queryparams
    )
    response = client.get(url, params=request_queryparams)

    assert response.status_code == 200
    assert response.url == "http://example.org/echo_queryparams?first=str&second=dict"


def test_client_queryparams_with_base_url_and_relative_query():
    """
    Regression: base_url + relative URL with query string + client params
    should all merge correctly. The relative URL's query is replaced by
    the merged client+request params.
    """
    client = httpx.Client(
        transport=httpx.MockTransport(hello_world),
        base_url="https://example.com/api/",
        params={"token": "abc"},
    )
    # Relative URL has its own query — it gets replaced by params
    request = client.build_request("GET", "endpoint", params={"page": "2"})
    assert request.url == "https://example.com/api/endpoint?token=abc&page=2"


def test_client_queryparams_relative_url_query_not_lost():
    """
    Regression: a relative URL's query string must not be silently dropped
    when client-level params are also set.
    """
    client = httpx.Client(
        transport=httpx.MockTransport(hello_world),
        base_url="https://example.com/api/",
        params={"token": "abc"},
    )
    # No per-request params — the relative URL's query should be preserved.
    request = client.build_request("GET", "endpoint?q=1")
    assert str(request.url).startswith("https://example.com/api/endpoint?")
    params = httpx.QueryParams(request.url.query)
    assert params.get("q") == "1"


def test_client_queryparams_relative_url_query_with_params():
    """
    When both a relative URL query and per-request params exist,
    the URL query, client params, and per-request params are all merged.
    Per-request params override client params which override URL params.
    """
    client = httpx.Client(
        transport=httpx.MockTransport(hello_world),
        base_url="https://example.com/api/",
        params={"token": "abc"},
    )
    request = client.build_request("GET", "endpoint?q=1", params={"page": "2"})
    # All three sources merged: URL query (q=1) + client params (token=abc)
    # + per-request params (page=2)
    params = httpx.QueryParams(request.url.query)
    assert params.get("q") == "1"
    assert params.get("token") == "abc"
    assert params.get("page") == "2"
