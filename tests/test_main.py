import os
import typing

from click.testing import CliRunner

import httpx


def splitlines(output: str) -> typing.Iterable[str]:
    return [line.strip() for line in output.splitlines()]


def remove_date_header(lines: typing.Iterable[str]) -> typing.Iterable[str]:
    return [line for line in lines if not line.startswith("date:")]


def test_help():
    runner = CliRunner()
    result = runner.invoke(httpx.main, ["--help"])
    assert result.exit_code == 0
    assert "A next generation HTTP client." in result.output


def test_get(server):
    url = str(server.url)
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url])
    assert result.exit_code == 0
    assert remove_date_header(splitlines(result.output)) == [
        "HTTP/1.1 200 OK",
        "server: uvicorn",
        "content-type: text/plain",
        "Transfer-Encoding: chunked",
        "",
        "Hello, world!",
    ]


def test_json(server):
    url = str(server.url.copy_with(path="/json"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url])
    assert result.exit_code == 0
    assert remove_date_header(splitlines(result.output)) == [
        "HTTP/1.1 200 OK",
        "server: uvicorn",
        "content-type: application/json",
        "Transfer-Encoding: chunked",
        "",
        "{",
        '"Hello": "world!"',
        "}",
    ]


def test_binary(server):
    url = str(server.url.copy_with(path="/echo_binary"))
    runner = CliRunner()
    content = "Hello, world!"
    result = runner.invoke(httpx.main, [url, "-c", content])
    assert result.exit_code == 0
    assert remove_date_header(splitlines(result.output)) == [
        "HTTP/1.1 200 OK",
        "server: uvicorn",
        "content-type: application/octet-stream",
        "Transfer-Encoding: chunked",
        "",
        f"<{len(content)} bytes of binary data>",
    ]


def test_redirects(server):
    url = str(server.url.copy_with(path="/redirect_301"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url])
    assert result.exit_code == 1
    assert remove_date_header(splitlines(result.output)) == [
        "HTTP/1.1 301 Moved Permanently",
        "server: uvicorn",
        "location: /",
        "Transfer-Encoding: chunked",
        "",
    ]


def test_follow_redirects(server):
    url = str(server.url.copy_with(path="/redirect_301"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "--follow-redirects"])
    assert result.exit_code == 0
    # Only the final response headers are shown; intermediate redirect
    # responses are not displayed in non-verbose mode.
    assert remove_date_header(splitlines(result.output)) == [
        "HTTP/1.1 200 OK",
        "server: uvicorn",
        "content-type: text/plain",
        "Transfer-Encoding: chunked",
        "",
        "Hello, world!",
    ]


def test_post(server):
    url = str(server.url.copy_with(path="/echo_body"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "-m", "POST", "-j", '{"hello": "world"}'])
    assert result.exit_code == 0
    assert remove_date_header(splitlines(result.output)) == [
        "HTTP/1.1 200 OK",
        "server: uvicorn",
        "content-type: text/plain",
        "Transfer-Encoding: chunked",
        "",
        '{"hello":"world"}',
    ]


def test_verbose(server):
    url = str(server.url)
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "-v"])
    assert result.exit_code == 0
    assert remove_date_header(splitlines(result.output)) == [
        "* Connecting to '127.0.0.1'",
        "* Connected to '127.0.0.1' on port 8000",
        "GET / HTTP/1.1",
        f"Host: {server.url.netloc.decode('ascii')}",
        "Accept: */*",
        "Accept-Encoding: gzip, deflate, br, zstd",
        "Connection: keep-alive",
        f"User-Agent: python-httpx/{httpx.__version__}",
        "",
        "HTTP/1.1 200 OK",
        "server: uvicorn",
        "content-type: text/plain",
        "Transfer-Encoding: chunked",
        "",
        "Hello, world!",
    ]


def test_auth(server):
    url = str(server.url)
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "-v", "--auth", "username", "password"])
    print(result.output)
    assert result.exit_code == 0
    assert remove_date_header(splitlines(result.output)) == [
        "* Connecting to '127.0.0.1'",
        "* Connected to '127.0.0.1' on port 8000",
        "GET / HTTP/1.1",
        f"Host: {server.url.netloc.decode('ascii')}",
        "Accept: */*",
        "Accept-Encoding: gzip, deflate, br, zstd",
        "Connection: keep-alive",
        f"User-Agent: python-httpx/{httpx.__version__}",
        "Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=",
        "",
        "HTTP/1.1 200 OK",
        "server: uvicorn",
        "content-type: text/plain",
        "Transfer-Encoding: chunked",
        "",
        "Hello, world!",
    ]


def test_download(server):
    url = str(server.url)
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(httpx.main, [url, "--download", "index.txt"])
        assert os.path.exists("index.txt")
        with open("index.txt", "r") as input_file:
            assert input_file.read() == "Hello, world!"


def test_errors():
    runner = CliRunner()
    result = runner.invoke(httpx.main, ["invalid://example.org"])
    assert result.exit_code == 1
    assert splitlines(result.output) == [
        "UnsupportedProtocol: Request URL has not an unsupported protocol 'invalid://'.",
    ]


def test_verbose_follow_redirects(server):
    """
    In verbose mode with --follow-redirects, the full redirect chain should be
    shown: request and response headers for each intermediate hop, then the
    final response headers and body.
    """
    url = str(server.url.copy_with(path="/redirect_301"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "-v", "--follow-redirects"])
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))

    # Connection info for the first hop
    assert lines[0] == "* Connecting to '127.0.0.1'"
    assert lines[1] == "* Connected to '127.0.0.1' on port 8000"

    # First request headers
    assert lines[2] == "GET /redirect_301 HTTP/1.1"

    # Find the intermediate redirect response headers
    redirect_idx = None
    for i, line in enumerate(lines):
        if line == "HTTP/1.1 301 Moved Permanently":
            redirect_idx = i
            break
    assert redirect_idx is not None, "Should show 301 redirect response"
    assert lines[redirect_idx + 1] == "server: uvicorn"
    assert lines[redirect_idx + 2] == "location: /"

    # Find the redirect marker line ("> GET ..." for the next hop)
    marker_idx = None
    for i, line in enumerate(lines):
        if line.startswith("> GET"):
            marker_idx = i
            break
    assert marker_idx is not None, "Should show redirect marker for next hop"

    # Second request headers (after redirect)
    assert lines[marker_idx + 1] == "GET / HTTP/1.1"

    # Final response headers
    final_idx = None
    for i, line in enumerate(lines):
        if line == "HTTP/1.1 200 OK":
            final_idx = i
            break
    assert final_idx is not None, "Should show final 200 response"

    # Final body
    assert "Hello, world!" in lines


def test_download_with_redirects(server):
    """
    When downloading with --follow-redirects, the file should contain the
    final response body (not intermediate redirect bodies), and the output
    should show only the final response headers.
    """
    url = str(server.url.copy_with(path="/redirect_301"))
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            httpx.main, [url, "--follow-redirects", "--download", "output.txt"]
        )
        assert result.exit_code == 0
        assert os.path.exists("output.txt")
        with open("output.txt", "r") as f:
            assert f.read() == "Hello, world!"

    # Verify only final response headers are shown (no intermediate 301)
    output_lines = remove_date_header(splitlines(result.output))
    # Should NOT contain the 301 response headers
    assert "HTTP/1.1 301 Moved Permanently" not in output_lines
    # Should contain the final 200 response headers
    assert "HTTP/1.1 200 OK" in output_lines


def test_verbose_download(server):
    """
    Verbose mode with --download should show request headers and final
    response headers, and save the file correctly.
    """
    url = str(server.url)
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(httpx.main, [url, "-v", "--download", "index.txt"])
        assert result.exit_code == 0
        assert os.path.exists("index.txt")
        with open("index.txt", "r") as f:
            assert f.read() == "Hello, world!"

    output_lines = remove_date_header(splitlines(result.output))
    # Should contain verbose connection info
    assert "* Connecting to '127.0.0.1'" in output_lines
    # Should contain request headers
    assert "GET / HTTP/1.1" in output_lines
    # Should contain final response headers
    assert "HTTP/1.1 200 OK" in output_lines
