from solcoder.core.logs import LogBuffer


def test_log_buffer_redacts_base58() -> None:
    buffer = LogBuffer()
    entry = buffer.record("wallet", "Secret address VkgXGe7czUXXcWzeWgt6H9VxLJhqioU5AnqRC1Ry2GK")
    assert "VkgX…y2GK" in entry.message
    assert "VkgXGe7czUXXcWzeWgt6H9VxLJhqioU5AnqRC1Ry2GK" not in entry.message


def test_log_buffer_recent_filters_and_limits() -> None:
    buffer = LogBuffer(max_entries=5)
    buffer.record("wallet", "w1")
    buffer.record("deploy", "d1")
    buffer.record("wallet", "w2")
    buffer.record("build", "b1")
    recent_wallet = buffer.recent(category="wallet", limit=5)
    assert [entry.message for entry in recent_wallet] == ["w1", "w2"]
    latest = buffer.latest()
    assert latest is not None and latest.message == "b1"


def test_log_buffer_normalizes_invalid_inputs() -> None:
    buffer = LogBuffer()
    entry = buffer.record("custom", "message", severity="verbose")
    assert entry.category == "system"
    assert entry.severity == "info"
