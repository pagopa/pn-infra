"""Offline behavior checks using real PyIceberg metadata and transactions."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

from pyiceberg.exceptions import ValidationError
from pyiceberg.partitioning import UNPARTITIONED_PARTITION_SPEC
from pyiceberg.schema import Schema
from pyiceberg.table import Table, Transaction
from pyiceberg.table.metadata import new_table_metadata
from pyiceberg.table.sorting import UNSORTED_SORT_ORDER
from pyiceberg.types import NestedField

import s3tables_update_schema as utility


class UpdateSchemaTest(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.path = Path(self.workspace.name) / "changes.json"
        self.changes = {"add": {"newFieldOne": "string", "newFieldTwo": "string", "newFieldThree": "string"}}
        self.path.write_text(json.dumps(self.changes))
        self.uuid = UUID("36d3cf61-1da9-43aa-b8d3-e49d71f869cb")
        schema = Schema(
            NestedField(field_id=1, name="eventId", field_type="string", required=False),
            NestedField(field_id=2, name="eventType", field_type="string", required=False),
            NestedField(field_id=3, name="createdAt", field_type="string", required=False),
            NestedField(field_id=4, name="counter", field_type="int", required=False),
        )
        self.catalog = Mock()
        self.table = Table(
            identifier=("example", "events"),
            metadata=new_table_metadata(schema, UNPARTITIONED_PARTITION_SPEC,
                                        UNSORTED_SORT_ORDER, "s3://offline-table", table_uuid=self.uuid),
            metadata_location="s3://offline-table/metadata.json", io=Mock(), catalog=self.catalog,
        )
        self.catalog.load_table.return_value = self.table
        self.session = Mock()
        self.session.client.return_value.get_caller_identity.return_value = {"Account": "089813480515"}
        self.arguments = [
            "--profile", "offline-profile",
            "--bucket-arn", "arn:aws:s3tables:eu-south-1:089813480515:bucket/offline-table",
            "--table", "example.events", "--changes", str(self.path),
            "--expect-uuid", str(self.uuid),
        ]

    def run_mode(self, *mode, answer=None):
        output = io.StringIO()
        with patch.object(utility.boto3, "Session", return_value=self.session), \
             patch.object(utility, "load_catalog", return_value=self.catalog), \
             patch("builtins.input", return_value=answer) as prompt, \
             contextlib.redirect_stdout(output):
            if answer is None:
                prompt.side_effect = AssertionError("Unexpected confirmation prompt.")
            elif callable(answer) or isinstance(answer, BaseException):
                prompt.side_effect = answer
            result = utility.main(self.arguments + list(mode))
        return result, output.getvalue()

    def assert_no_commit(self):
        self.catalog.commit_table.assert_not_called()

    def test_default_and_explicit_dry_run_do_not_commit_or_mutate_metadata(self):
        before = self.table.metadata.model_dump_json()
        for mode in ((), ("--dry-run",)):
            result, output = self.run_mode(*mode)
            self.assertEqual(result, 0)
            self.assertIn("Columns: 4 -> 7", output)
            self.assertIn("DRY RUN", output)
            self.assertEqual(self.table.metadata.model_dump_json(), before)
        self.assert_no_commit()

    def test_check_before_apply_returns_one_without_staging_or_commit(self):
        with patch.object(self.table, "transaction", side_effect=AssertionError("Check must not stage")):
            result, output = self.run_mode("--check")
        self.assertEqual(result, 1)
        self.assertIn("CHECK PENDING", output)
        self.assert_no_commit()

    def test_three_additions_preserve_all_original_definitions_and_ids(self):
        original = self.table.schema().fields
        transaction, proposed = utility.stage_changes(self.table, self.changes)
        self.assertEqual(proposed.fields[:4], original)
        self.assertEqual([field.name for field in proposed.fields[4:]], list(self.changes["add"]))
        self.assertEqual([field.field_id for field in proposed.fields[4:]], [5, 6, 7])
        self.assertEqual(self.table.schema().fields, original)
        self.assertEqual(transaction.table_metadata.snapshots, self.table.metadata.snapshots)
        self.assert_no_commit()

    def test_apply_commits_once_verifies_then_repeat_and_check_do_not_commit(self):
        def simulated_commit(transaction):
            self.table.metadata = transaction.table_metadata
            return self.table

        with patch.object(Transaction, "commit_transaction", autospec=True, side_effect=simulated_commit) as commit, \
             patch.object(self.table, "refresh") as refresh:
            result, output = self.run_mode("--apply", answer="yes")
            self.assertEqual(result, 0)
            self.assertIn("APPLIED AND VERIFIED", output)
            commit.assert_called_once()
            refresh.assert_called_once()
            self.assertEqual(self.run_mode("--check")[0], 0)
            self.assertIn("ALREADY ALIGNED", self.run_mode("--apply")[1])
            commit.assert_called_once()

    def test_preview_shows_only_effective_changes_and_selected_file(self):
        result, output = self.run_mode("--dry-run")
        self.assertEqual(result, 0)
        self.assertIn(f"Changes file: {self.path.resolve()}", output)
        for name in self.changes["add"]:
            self.assertIn(f"  + {name} string", output)
        for name in ["eventId", "eventType", "createdAt", "counter"]:
            self.assertNotIn(name, output)
        self.assertNotIn("Proposed schema (all columns)", output)
        self.assertNotIn("Requested changes:", output)
        self.assert_no_commit()

    def test_apply_shows_proposal_before_confirmation_and_commits_reviewed_input(self):
        before = self.table.metadata.model_dump_json()

        def review(prompt):
            self.assertIn("Type 'yes'", prompt)
            preview = output.getvalue()
            self.assertIn(f"Changes file: {self.path.resolve()}", preview)
            for name in self.changes["add"]:
                self.assertIn(f"  + {name} string", preview)
            self.assertNotIn("eventId", preview)
            self.assertEqual(self.table.metadata.model_dump_json(), before)
            commit.assert_not_called()
            self.path.write_text(json.dumps({"add": {"unreviewedField": "string"}}))
            return "yes"

        def simulated_commit(transaction):
            self.assertEqual([field.name for field in transaction.table_metadata.schema().fields[4:]],
                             list(self.changes["add"]))
            self.table.metadata = transaction.table_metadata

        output = io.StringIO()
        with patch.object(utility.boto3, "Session", return_value=self.session), \
             patch.object(utility, "load_catalog", return_value=self.catalog), \
             patch("builtins.input", side_effect=review) as prompt, \
             patch.object(Transaction, "commit_transaction", autospec=True, side_effect=simulated_commit) as commit, \
             patch.object(self.table, "refresh"), contextlib.redirect_stdout(output):
            self.assertEqual(utility.main(self.arguments + ["--apply"]), 0)
        prompt.assert_called_once()
        commit.assert_called_once()
        self.assertIn("APPLIED AND VERIFIED", output.getvalue())

    def test_apply_cancels_without_commit_on_nonaffirmative_answers(self):
        before = self.table.metadata.model_dump_json()
        with patch.object(Transaction, "commit_transaction") as commit:
            for answer in ("", "no", "y", "YES", "yes please"):
                with self.subTest(answer=answer):
                    result, output = self.run_mode("--apply", answer=answer)
                    self.assertEqual(result, 1)
                    self.assertIn("CANCELLED: no commit sent.", output)
                    self.assertNotIn("APPLIED AND VERIFIED", output)
                    self.assertEqual(self.table.metadata.model_dump_json(), before)
            commit.assert_not_called()
        self.assert_no_commit()

    def test_apply_cancels_without_commit_on_eof_or_interrupt(self):
        before = self.table.metadata.model_dump_json()
        with patch.object(Transaction, "commit_transaction") as commit:
            for answer in (EOFError(), KeyboardInterrupt()):
                with self.subTest(answer=type(answer).__name__):
                    result, output = self.run_mode("--apply", answer=answer)
                    self.assertEqual(result, 1)
                    self.assertIn("CANCELLED: no commit sent.", output)
                    self.assertEqual(self.table.metadata.model_dump_json(), before)
            commit.assert_not_called()
        self.assert_no_commit()

    def test_apply_requires_uuid_and_modes_are_exclusive(self):
        no_uuid = self.arguments[:-2]
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                utility.parse_args(no_uuid + ["--apply"])
            self.assertEqual(error.exception.code, 2)
            with self.assertRaises(SystemExit):
                utility.parse_args(self.arguments + ["--check", "--apply"])
        self.assert_no_commit()

    def test_uuid_and_account_mismatch_stop_before_commit(self):
        self.arguments[-1] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaisesRegex(ValueError, "UUID"):
            self.run_mode("--apply")
        self.session.client.return_value.get_caller_identity.return_value = {"Account": "956319218727"}
        with self.assertRaisesRegex(ValueError, "account"):
            self.run_mode("--apply")
        self.assert_no_commit()

    def test_duplicate_json_keys_are_rejected(self):
        self.path.write_text('{"add":{"newField":"string","newField":"long"}}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            utility.read_changes(self.path)
        self.assert_no_commit()

    def test_invalid_or_ambiguous_changes_are_rejected(self):
        invalid = [[], {}, {"drop": {"eventId": "string"}}, {"add": []},
                   {"add": {}}, {"add": {"nested.field": "string"}},
                   {"add": {"newField": "string"}, "types": {"newField": "long"}},
                   {"rename": {"eventId": "eventId"}}, {"add": {"newField": {"type": "struct"}}}]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                utility.validate_changes(changes)
        self.assert_no_commit()

    def test_existing_column_with_different_definition_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, "different definition"):
            utility.stage_changes(self.table, {"add": {"eventId": "long"}})
        self.assert_no_commit()

    def test_case_collision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "letter case"):
            utility.stage_changes(self.table, {"add": {"eventid": "string"}})
        self.assert_no_commit()

    def test_rename_and_promotion_preserve_ids_and_unrelated_fields(self):
        original = self.table.schema().fields
        transaction, schema = utility.stage_changes(self.table, {
            "rename": {"eventId": "eventID"}, "types": {"counter": "long"},
        })
        self.assertEqual(schema.find_field("eventID").field_id, 1)
        self.assertEqual(schema.find_field("counter").field_id, 4)
        self.assertEqual(schema.fields[1:3], original[1:3])
        self.path.write_text(json.dumps({"rename": {"eventId": "eventID"}, "types": {"counter": "long"}}))
        self.assertEqual(self.run_mode("--check")[0], 1)
        self.table.metadata = transaction.table_metadata
        self.assertEqual(self.run_mode("--check")[0], 0)
        self.assert_no_commit()

    def test_preview_identifies_rename_and_previous_type(self):
        self.path.write_text(json.dumps({"rename": {"eventId": "eventID"}, "types": {"counter": "long"}}))
        result, output = self.run_mode("--dry-run")
        self.assertEqual(result, 0)
        self.assertIn("  ~ eventId -> eventID (string)", output)
        self.assertIn("  ~ counter: int -> long", output)
        self.assertNotIn("eventType", output)
        self.assertNotIn("createdAt", output)
        self.assert_no_commit()

    def test_incompatible_type_promotion_is_rejected(self):
        with self.assertRaises(ValidationError):
            utility.stage_changes(self.table, {"types": {"eventId": "long"}})
        self.assert_no_commit()

    def test_failed_commit_does_not_report_success(self):
        with patch.object(Transaction, "commit_transaction", side_effect=RuntimeError("commit error")), \
             self.assertRaisesRegex(RuntimeError, "outcome unknown"):
            self.run_mode("--apply", answer="yes")

    def test_post_commit_schema_mismatch_is_reported(self):
        with patch.object(Transaction, "commit_transaction"), patch.object(self.table, "refresh"), \
             self.assertRaisesRegex(RuntimeError, "verification differs"):
            self.run_mode("--apply", answer="yes")


if __name__ == "__main__":
    unittest.main()
