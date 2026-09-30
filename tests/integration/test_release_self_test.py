from __future__ import annotations

import json

from stem_crop_tool.release_self_test import (
    REPORT_NAME,
    run_release_self_test,
    write_failure_report,
)


def test_release_self_test_exercises_core_packaged_matrix(tmp_path) -> None:
    report_path = run_release_self_test(tmp_path)

    assert report_path == tmp_path / REPORT_NAME
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["inputs"] == [
        "npy",
        "npy_stack",
        "png_uint16",
        "jpeg_uint8",
    ]
    assert payload["outputs"] == [
        "npy",
        "png_uint16",
        "npy_batch",
        "json_sidecar",
        "json_manifest",
    ]
    assert payload["external_dm_tested"] is False


def test_release_self_test_failure_is_machine_readable(tmp_path) -> None:
    error = RuntimeError("deliberate packaged-test failure")

    report_path = write_failure_report(tmp_path, error)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["error"] == str(error)
    assert "RuntimeError: deliberate packaged-test failure" in payload["traceback"]
