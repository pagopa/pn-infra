#!/usr/bin/env python3
"""Update one S3 Tables schema with PyIceberg; default mode is dry-run."""

import argparse
import json
import re
import sys
from pathlib import Path
from uuid import UUID

import boto3
from pyiceberg.catalog import load_catalog
from pyiceberg.types import NestedField, PrimitiveType


def field_type(name, kind):
    """Parse a primitive Iceberg type without assigning a real table field ID."""
    if not isinstance(kind, str) or not kind:
        raise ValueError(f"Column {name}: expected an Iceberg type string.")
    parsed = NestedField(field_id=1, name=name, field_type=kind).field_type
    if not isinstance(parsed, PrimitiveType):
        raise ValueError("Only primitive column types are supported.")
    return parsed


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_changes(changes):
    """Reject unsupported operations, nested paths and overlapping edits."""
    if not isinstance(changes, dict) or not changes or set(changes) - {"add", "rename", "types"}:
        raise ValueError("Use a JSON object containing only add, rename and types.")
    touched = set()
    for operation, columns in changes.items():
        if not isinstance(columns, dict):
            raise ValueError(f"{operation} must be an object of column names and values.")
        for name, value in columns.items():
            names = [name, value] if operation == "rename" else [name]
            if any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) for n in names):
                raise ValueError("Use top-level column names containing letters, digits and underscores.")
            affected = {n.casefold() for n in names}
            if affected & touched:
                raise ValueError(f"Overlapping column changes: {name}")
            touched.update(affected)
            if operation == "rename":
                if name == value:
                    raise ValueError(f"Rename source and destination are identical: {name}")
            else:
                field_type(name, value)
    if not touched:
        raise ValueError("The changes file contains no column operations.")
    return changes


def read_changes(path):
    return validate_changes(json.loads(path.read_text(), object_pairs_hook=unique_keys))


def pending_changes(schema, changes):
    """Check requested definitions only; extra existing columns are allowed."""
    fields = {field.name: field for field in schema.fields}
    pending = []
    for name, kind in changes.get("add", {}).items():
        field = fields.get(name)
        if field is None or field.field_type != field_type(name, kind) or field.required:
            pending.append(f"ADD {name}: optional {kind}")
    for old, new in changes.get("rename", {}).items():
        if old in fields or new not in fields:
            pending.append(f"RENAME {old} -> {new}")
    for name, kind in changes.get("types", {}).items():
        if name not in fields or fields[name].field_type != field_type(name, kind):
            pending.append(f"TYPE {name} -> {kind}")
    return pending


def stage_changes(table, changes):
    """Build a proposed schema locally; do not enter the transaction context."""
    validate_changes(changes)
    fields = {field.name: field for field in table.schema().fields}
    transaction = table.transaction()
    with transaction.update_schema(case_sensitive=True) as update:
        for name, kind in changes.get("add", {}).items():
            expected = field_type(name, kind)
            if name in fields:
                if fields[name].field_type != expected or fields[name].required:
                    raise ValueError(f"Existing column {name} has a different definition.")
                continue
            update.add_column(name, expected, required=False)
        for old, new in changes.get("rename", {}).items():
            update.rename_column(old, new)
        for name, kind in changes.get("types", {}).items():
            update.update_column(name, field_type=field_type(name, kind))
    proposed = transaction.table_metadata.schema()
    names = [field.name.casefold() for field in proposed.fields]
    if len(names) != len(set(names)):
        raise ValueError("Column names cannot differ only by letter case.")
    return transaction, proposed


def print_preview(before, proposed):
    print(f"Columns: {len(before.fields)} -> {len(proposed.fields)}")
    print("Schema changes:")
    original = {field.field_id: field for field in before.fields}
    for field in proposed.fields:
        previous = original.get(field.field_id)
        if previous is None:
            print(f"  + {field.name} {field.field_type}")
        else:
            if previous.name != field.name:
                print(f"  ~ {previous.name} -> {field.name} ({field.field_type})")
            if previous.field_type != field.field_type:
                print(f"  ~ {field.name}: {previous.field_type} -> {field.field_type}")
    if before.fields == proposed.fields:
        print("  None")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--profile", "-p", required=True, help="AWS profile from ~/.aws/config")
    parser.add_argument("--bucket-arn", required=True, help="S3 Tables bucket ARN, including region and account")
    parser.add_argument("--table", required=True, help="One table: NAMESPACE.TABLE")
    parser.add_argument("--changes", required=True, type=Path, help="JSON containing only requested column changes")
    parser.add_argument("--expect-uuid", type=UUID, help="Expected Iceberg table UUID; required for --apply")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", dest="mode", action="store_const", const="dry-run", help="Preview without committing (default)")
    modes.add_argument("--check", dest="mode", action="store_const", const="check", help="Check requested definitions: 0 aligned, 1 pending")
    modes.add_argument("--apply", dest="mode", action="store_const", const="apply", help="Preview, ask for confirmation, commit and verify the schema")
    parser.set_defaults(mode="dry-run")
    args = parser.parse_args(argv)
    bucket = re.fullmatch(r"arn:aws:s3tables:([a-z0-9-]+):(\d{12}):bucket/([a-z0-9-]+)", args.bucket_arn)
    if not bucket:
        parser.error("Expected an AWS S3 Tables bucket ARN.")
    args.region, args.account, args.bucket = bucket.groups()
    if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", args.table):
        parser.error("Use exactly one namespace.table, with lowercase names.")
    if args.mode == "apply" and args.expect_uuid is None:
        parser.error("--apply requires --expect-uuid.")
    return args


def main(argv=None):
    args = parse_args(argv)
    changes_path = args.changes.resolve()
    changes = read_changes(changes_path)
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.account:
        raise ValueError("The AWS profile account does not match the bucket ARN.")
    catalog = load_catalog("s3tables", **{
        "type": "rest", "uri": f"https://s3tables.{args.region}.amazonaws.com/iceberg",
        "warehouse": args.bucket_arn, "client.profile-name": args.profile,
        "rest.sigv4-enabled": "true", "rest.signing-name": "s3tables",
        "rest.signing-region": args.region,
    })
    table = catalog.load_table(tuple(args.table.split(".")))
    if args.expect_uuid and table.metadata.table_uuid != args.expect_uuid:
        raise ValueError("Unexpected table UUID.")
    before = table.schema()
    print(f"Mode: {args.mode}; profile: {args.profile}")
    print(f"Account: {args.account}; region: {args.region}; bucket: {args.bucket}; table: {args.table}")
    print(f"UUID: {table.metadata.table_uuid}; current columns: {len(before.fields)}")
    print(f"Changes file: {changes_path}")
    if args.mode == "check":
        pending = pending_changes(before, changes)
        print("\n".join(pending) if pending else "CHECK OK: requested definitions are present.")
        if pending:
            print("CHECK PENDING: requested definitions do not match; no changes applied.")
        return int(bool(pending))
    transaction, proposed = stage_changes(table, changes)
    print_preview(before, proposed)
    if before.fields == proposed.fields:
        print("ALREADY ALIGNED: no commit needed.")
    elif args.mode == "dry-run":
        print("DRY RUN: proposed schema validated locally; no commit sent.")
    else:
        try:
            confirmed = input("\nType 'yes' to apply this schema [default: cancel]: ").strip() == "yes"
        except (EOFError, KeyboardInterrupt):
            confirmed = False
            print()
        if not confirmed:
            print("CANCELLED: no commit sent.")
            return 1
        try:
            transaction.commit_transaction()
        except Exception as error:
            raise RuntimeError(f"Commit failed or outcome unknown: {error}. Inspect with --check before retrying.") from error
        table.refresh()
        if table.metadata.table_uuid != args.expect_uuid or table.schema().fields != proposed.fields:
            raise RuntimeError("Commit sent but verification differs; inspect before retrying.")
        print("APPLIED AND VERIFIED: names, field IDs and types match the proposed schema.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)
