"""Versioned IAM Access Analyzer mutelist loaded from pn-configuration."""

import hashlib
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

from fine_grained_exclusions import parse_rules


GITHUB_API_VERSION = "2022-11-28"


def _empty_mutelist():
    return {
        "loaded": False,
        "archive_role_patterns": [],
        "fine_grained_exclusions": [],
    }


def _parse_json(content):
    return json.loads(content)


def validate_mutelist(document):
    """Validate the JSON document and normalize both exclusion mechanisms."""
    if not isinstance(document, dict):
        raise ValueError("configuration root must be an object")
    if document.get("schemaVersion") != 1:
        raise ValueError("schemaVersion must be 1")

    archive_role_patterns = document.get("archiveRolePatterns", [])
    if not isinstance(archive_role_patterns, list):
        raise ValueError("archiveRolePatterns must be an array")
    if any(
        not isinstance(pattern, str) or not pattern.strip()
        for pattern in archive_role_patterns
    ):
        raise ValueError("archiveRolePatterns contains an invalid pattern")

    return {
        "loaded": True,
        "archive_role_patterns": [
            pattern.strip() for pattern in archive_role_patterns
        ],
        "fine_grained_exclusions": parse_rules(
            document.get("fineGrainedExclusions", [])
        ),
    }


def load_mutelist(
    *, secrets_client, github_token_name, repository, commit_id, path, logger,
    urlopen_fn=urlopen
):
    """Download and validate the mutelist, failing open on any error."""
    try:
        token_response = secrets_client.get_secret_value(SecretId=github_token_name)
        github_token = _extract_github_token(token_response.get("SecretString", ""))
        if not github_token:
            raise ValueError("GitHub token secret is empty")

        encoded_path = quote(path, safe="/")
        encoded_commit = quote(commit_id, safe="")
        url = (
            f"https://api.github.com/repos/{repository}/contents/{encoded_path}"
            f"?ref={encoded_commit}"
        )
        request = Request(url, headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        })
        with urlopen_fn(request, timeout=15) as response:
            content = response.read()
        document = _parse_json(content.decode("utf-8"))
        mutelist = validate_mutelist(document)
        content_sha256 = hashlib.sha256(content).hexdigest()
        logger.info(json.dumps({
            "msg": "IAM Access Analyzer mutelist loaded",
            "repository": repository,
            "commit_id": commit_id,
            "path": path,
            "sha256": content_sha256,
            "archive_role_patterns": len(mutelist["archive_role_patterns"]),
            "fine_grained_exclusions": len(mutelist["fine_grained_exclusions"]),
        }))
        return mutelist
    except Exception as exc:
        logger.warning(json.dumps({
            "msg": "IAM Access Analyzer mutelist unavailable; fine-grained exclusions disabled",
            "repository": repository,
            "commit_id": commit_id,
            "path": path,
            "error": str(exc),
        }))
        return _empty_mutelist()


def _extract_github_token(secret_string):
    """Support both a raw token and the JSON secret formats used by PN tooling."""
    if not isinstance(secret_string, str) or not secret_string:
        return ""
    try:
        secret = json.loads(secret_string)
    except json.JSONDecodeError:
        return secret_string
    if not isinstance(secret, dict):
        return ""
    for key in ("GITHUB_TOKEN", "githubToken", "github_token", "token"):
        token = secret.get(key)
        if isinstance(token, str) and token:
            return token
    return ""
