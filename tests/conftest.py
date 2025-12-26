"""Pytest configuration and fixtures."""

import http.server
import socketserver
import threading

import pytest

from tests.snapshot_helper import SnapshotAssertion


@pytest.fixture(autouse=True)
def reset_simplekml_ids():
    """Reset simplekml's global ID counter before each test.

    This ensures deterministic KML IDs regardless of test execution order,
    preventing spurious snapshot mismatches.
    """
    import simplekml.base

    simplekml.base.Kmlable._globalid = 0
    yield
    # Counter will be reset before next test


def pytest_addoption(parser):
    """Add pytest command line options."""
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update snapshot files instead of comparing",
    )


@pytest.fixture
def update_snapshots(request):
    """Fixture to check if snapshots should be updated."""
    return request.config.getoption("--update-snapshots")


@pytest.fixture
def snapshot(request):
    """
    Fixture for snapshot testing.

    Usage:
        def test_example(snapshot):
            # Generate KMZ
            kmz_path = generate_kmz()
            # Assert it matches snapshot
            snapshot.assert_match(kmz_path)
    """
    test_name = request.node.name
    update_snapshots_flag = request.config.getoption("--update-snapshots")

    return SnapshotAssertion(test_name, update_snapshots_flag)


@pytest.fixture
def tile_server(tmp_path):
    """
    Fixture for creating a local tile server for testing.

    Automatically starts an HTTP server serving tiles from a temporary directory
    and cleans up when the test completes.

    Usage:
        def test_custom_tiles(tile_server):
            # Create test tile
            tile_path = tile_server.fixtures_dir / "12" / "3641" / "1613.png"
            tile_path.parent.mkdir(parents=True)
            Image.new("RGBA", (256, 256), (255, 0, 0, 128)).save(tile_path)

            # Use in config
            url_template = f"http://127.0.0.1:{tile_server.port}/{{z}}/{{x}}/{{y}}.png"
            ...

    Attributes:
        port (int): The port the server is listening on
        fixtures_dir (Path): Directory where test tiles should be placed (z/x/y.png structure)
        url_template (str): Convenience property for standard tile URL template
    """

    class TileServer:
        def __init__(self, port, fixtures_dir, server, thread):
            self.port = port
            self.fixtures_dir = fixtures_dir
            self._server = server
            self._thread = thread

        @property
        def url_template(self):
            """Get the standard tile URL template for this server."""
            return f"http://127.0.0.1:{self.port}/{{z}}/{{x}}/{{y}}.png"

    # Create fixtures directory
    fixtures_dir = tmp_path / "tile_fixtures"
    fixtures_dir.mkdir()

    # Create HTTP request handler
    class TileHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(fixtures_dir), **kwargs)

        def log_message(self, format, *args):
            pass  # Suppress logging during tests

    # Start server on auto-assigned port
    server = socketserver.TCPServer(("127.0.0.1", 0), TileHTTPRequestHandler)
    port = server.server_address[1]

    # Start server thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Yield tile server instance to test
    tile_server_instance = TileServer(port, fixtures_dir, server, thread)
    yield tile_server_instance

    # Cleanup: shutdown server
    server.shutdown()
    server.server_close()
    thread.join(timeout=1.0)
