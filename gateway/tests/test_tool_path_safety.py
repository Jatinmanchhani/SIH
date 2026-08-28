import json
import pytest

from orchestrator import execute_tool, _resolve_in_sample_data, SAMPLE_DATA_ROOT
import file_tools, rag


@pytest.fixture
def rag_store():
    store = rag.SimpleTfidfStore()
    rag.ingest_directory(store, SAMPLE_DATA_ROOT)
    return store


def test_resolve_in_sample_data_allows_real_file():
    path = _resolve_in_sample_data("sample_inspection_scan.png")
    assert path.parent == SAMPLE_DATA_ROOT
    assert path.exists()


@pytest.mark.parametrize("malicious", [
    "../../etc/passwd",
    "../../../etc/passwd",
    "../../../../root/.ssh/id_rsa",
])
def test_resolve_in_sample_data_blocks_traversal(malicious):
    with pytest.raises(file_tools.PathEscapeError):
        _resolve_in_sample_data(malicious)


def test_extract_from_image_tool_blocks_traversal(rag_store):
    result = json.loads(execute_tool(
        "extract_from_image", {"relative_path": "../../etc/passwd"}, rag_store
    ))
    assert "error" in result


def test_generate_approval_note_tool_blocks_traversal(rag_store):
    result = json.loads(execute_tool(
        "generate_approval_note",
        {
            "title": "x", "reference_no": "../../../tmp/pwned",
            "prepared_for": "x", "findings": [], "recommendation": "x",
        },
        rag_store,
    ))
    assert "error" in result