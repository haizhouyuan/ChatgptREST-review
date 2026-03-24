from __future__ import annotations

from pathlib import Path


def test_feishu_ws_service_loads_shared_chatgptrest_env() -> None:
    source = Path("ops/systemd/chatgptrest-feishu-ws.service").read_text(
        encoding="utf-8"
    )
    assert "Environment=ADVISOR_API_URL=http://127.0.0.1:18711/v2/advisor/advise" in source
    assert "EnvironmentFile=-%h/.config/chatgptrest/chatgptrest.env" in source
    assert "EnvironmentFile=-/vol1/maint/MAIN/secrets/credentials.env" in source
    assert "python -m chatgptrest.advisor.feishu_ws_gateway" in source
