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


def test_client_queryparams_with_url_inline_query():
    client = httpx.Client(
        transport=httpx.MockTransport(hello_world), params={"token": "abc"}
    )
    request = client.build_request("GET", "http://example.org/path?page=1")
    assert request.url.params["page"] == "1"
    assert request.url.params["token"] == "abc"


def test_client_queryparams_override_url_inline_query():
    client = httpx.Client(
        transport=httpx.MockTransport(hello_world), params={"page": "99"}
    )
    request = client.build_request("GET", "http://example.org/path?page=1")
    assert request.url.params["page"] == "99"


def test_per_request_params_override_url_inline_query():
    client = httpx.Client(transport=httpx.MockTransport(hello_world))
    request = client.build_request(
        "GET", "http://example.org/path?page=1", params={"page": "2"}
    )
    assert request.url.params["page"] == "2"


def test_all_three_param_sources_merged():
    client = httpx.Client(
        transport=httpx.MockTransport(hello_world), params={"token": "abc"}
    )
    request = client.build_request(
        "GET", "http://example.org/path?page=1", params={"extra": "val"}
    )
    assert request.url.params["page"] == "1"
    assert request.url.params["token"] == "abc"
    assert request.url.params["extra"] == "val"


def test_url_inline_query_preserved_without_params():
    client = httpx.Client(transport=httpx.MockTransport(hello_world))
    request = client.build_request("GET", "http://example.org/path?page=1")
    assert request.url.params["page"] == "1"


def test_base_url_with_inline_query_and_params():
    client = httpx.Client(
        base_url="https://www.example.com/api/",
        transport=httpx.MockTransport(hello_world),
        params={"token": "abc"},
    )
    request = client.build_request("GET", "/users?page=1#section")
    assert request.url.params["page"] == "1"
    assert request.url.params["token"] == "abc"
    assert request.url.fragment == "section"
