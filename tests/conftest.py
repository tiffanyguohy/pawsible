"""CI must never depend on Petfinder's uptime or on spending money at Anthropic.

Convention is not enough: one forgotten `httpx.get` in a helper silently makes the
suite network-dependent, and it fails weeks later for reasons unrelated to the change
that exposed it. So sockets are banned by default and a test must opt out explicitly.
"""

from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def _ban_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("network"):
        return

    def _blocked(*args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "network access is disabled in tests; mark with @pytest.mark.network to opt out"
        )

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
