# S3 Tables update schema

Add columns, rename columns and promote compatible types in an existing
S3 Tables schema using PyIceberg. Supply only the requested changes.

## Installation

Python 3.10+ and a configured AWS profile with catalog access. Apply requires
schema update permissions.

```bash
cd scripts/s3tables-update-schema
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Usage

For SSO profiles, authenticate with AWS CLI:

```bash
aws sso login --profile "<profile>"
```

```bash
python s3tables_update_schema.py \
  --profile "<profile>" \
  --bucket-arn "arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>" \
  --table "<namespace>.<table>" \
  --changes changes.example.json \
  --expect-uuid "<iceberg-table-uuid>" \
  --dry-run
```

Account and region are derived from the bucket ARN. The profile account must
match. `--expect-uuid` identifies the Iceberg table and is required for apply.

- `--dry-run` (default): preview effective changes without committing.
- `--check`: verify the requested column definitions without committing.
- `--apply`: preview changes, require `yes`, commit and verify the resulting schema.

Modes are mutually exclusive. Preview uses `+ name type` for additions and `~`
for renames or type changes. Enter, any answer other than `yes`, EOF or Ctrl+C
at the confirmation prompt cancels apply. Identical additions do not commit.

## Changes

Example `changes.example.json`:

```json
{
  "add": {
    "newFieldOne": "string",
    "newFieldTwo": "string",
    "newFieldThree": "string"
  }
}
```

| Section | Operation | Entry example |
|---|---|---|
| `add` | Add optional columns | `"newField": "string"` |
| `rename` | Rename existing columns | `"oldName": "newName"` |
| `types` | Promote compatible types | `"counter": "long"` for an existing `int` |

Only top-level primitive columns are supported. Names are case-sensitive;
camelCase is preserved. Existing field IDs are preserved; additions receive
new IDs. Deletion is not supported. Data files are not rewritten; historical
rows return NULL for added columns.

## Notes

- Dry-run is a local preview, not an AWS DryRun API; it does not validate write permissions.
- After a failed or uncertain commit, run `--check` before retrying. No automatic rollback.
- CloudFormation templates are not updated. Changing `IcebergMetadata` requires
  [replacement](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3tables-table.html#cfn-s3tables-table-icebergmetadata).

Exit codes: `0` valid preview, aligned check or verified/no-op apply;
`1` pending check or cancelled apply; `2` error.

## Tests

```bash
python -m unittest discover -s tests -v
```

## References

- [AWS S3 Tables REST catalog](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-open-source.html)
- [PyIceberg schema changes](https://py.iceberg.apache.org/api/#schema-evolution)
