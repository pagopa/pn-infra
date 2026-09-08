from datetime import datetime, timedelta, timezone

import pytest

from athena import build_query
from manifest import actor_from, load_manifest, merge_records


NOW = datetime(2026, 8, 27, 10, 30, tzinfo=timezone.utc)


def record(event_id, timestamp, status="SUCCESS", role="DeployRole"):
    return {
        "eventId": event_id,
        "timestamp": timestamp,
        "environment": "dev",
        "status": status,
        "executionUser": {"type": "automation", "role": role, "displayName": "must disappear"},
    }


def test_query_uses_time_partitions_and_environment():
    query = build_query(
        "release_tracking_database",
        "pn_release_events_all",
        "dev",
        NOW - timedelta(hours=24),
        NOW,
    )

    assert "p_year ||" not in query
    assert "p_year = '2026' AND p_month = '08' AND p_day IN ('26', '27')" in query
    assert "p_hour IN ('00', '01', '02'" in query
    assert "environment = 'dev'" in query
    assert "ORDER BY" not in query


def test_query_partitions_support_year_change():
    query = build_query(
        "release_tracking_database",
        "pn_release_events_all",
        "dev",
        datetime(2025, 12, 31, 23, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc),
    )

    assert "p_year = '2025' AND p_month = '12' AND p_day IN ('31')" in query
    assert "p_year = '2026' AND p_month = '01' AND p_day IN ('01')" in query


def test_merge_deduplicates_prunes_and_removes_display_name():
    existing = [
        record("old", "2026-01-01T00:00:00Z"),
        record("same", "2026-08-26T08:00:00Z", status="FAILURE"),
    ]
    incoming = [
        record("same", "2026-08-26T08:05:00Z"),
        record("new", "2026-08-27T09:00:00Z"),
    ]

    merged = merge_records(existing, incoming, "dev", NOW - timedelta(days=180))

    assert [item["eventId"] for item in merged] == ["new", "same"]
    assert merged[1]["status"] == "SUCCESS"
    assert merged[0]["executionUser"] == {"type": "automation", "role": "DeployRole"}


def test_actor_keeps_role_but_drops_sso_session_identity():
    actor = actor_from(
        "arn:aws:sts::000000000000:assumed-role/AWSReservedSSO_Developer_abcdef/session-name"
    )

    assert actor == {"type": "human", "role": "Developer"}


def test_missing_manifest_is_an_empty_initial_state():
    class MissingManifestS3:
        class exceptions:
            class NoSuchKey(Exception):
                pass

        def get_object(self, **kwargs):
            raise self.exceptions.NoSuchKey()

    assert load_manifest(MissingManifestS3(), "bucket", "manifest.json", 1024) == (None, None)


def test_unexpected_manifest_read_error_is_not_hidden():
    class BrokenS3:
        class exceptions:
            class NoSuchKey(Exception):
                pass

        def get_object(self, **kwargs):
            raise RuntimeError("S3 unavailable")

    with pytest.raises(RuntimeError, match="S3 unavailable"):
        load_manifest(BrokenS3(), "bucket", "manifest.json", 1024)
