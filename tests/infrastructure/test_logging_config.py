from __future__ import annotations

import json

from loguru import logger

from job_search.infrastructure.logging import configure_logging


class TestConfigureLogging:
    def test_writes_structured_json_log(self, tmp_path):
        log_path = tmp_path / "raxy.jsonl"
        configure_logging(log_path=str(log_path), force=True, enqueue=False)

        logger.bind(component="test", portal="linkedin", jobs_count=3).info("search_finished")

        payload = json.loads(log_path.read_text(encoding="utf-8").strip())
        record = payload["record"]
        assert record["message"] == "search_finished"
        assert record["extra"]["component"] == "test"
        assert record["extra"]["portal"] == "linkedin"
        assert record["extra"]["jobs_count"] == 3

    def test_is_idempotent_without_force(self, tmp_path):
        first_path = tmp_path / "first.jsonl"
        second_path = tmp_path / "second.jsonl"
        configure_logging(log_path=str(first_path), force=True, enqueue=False)
        configure_logging(log_path=str(second_path), enqueue=False)

        logger.info("keeps_first_sink")

        assert first_path.exists()
        assert not second_path.exists()
