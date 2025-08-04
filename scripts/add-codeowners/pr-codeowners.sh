#!/bin/bash

REPOS_FILE="repos.txt"
BRANCH_NAME="feature/PN-15079-add-codeowners"
CODEOWNERS_FILE="CODEOWNERS"
COMMIT_MSG="PN-15079: chore - add CODEOWNERS file"
PR_TITLE="Add CODEOWNERS file"
PR_BODY="This PR adds a CODEOWNERS file to ensure proper code review routing."

# Check prerequisites
if ! command -v gh &>/dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    exit 1
fi

if [ ! -f "$CODEOWNERS_FILE" ]; then
    echo "❌ CODEOWNERS file not found."
    exit 1
fi

if [ ! -f "$REPOS_FILE" ]; then
    echo "❌ Repository list not found ($REPOS_FILE)."
    exit 1
fi

while read -r REPO; do
    echo "🔄 Processing $REPO"

    REPO_NAME=$(basename "$REPO")
    CLONE_DIR="tmp-$REPO_NAME"

    git clone "git@github.com:pagopa/$REPO.git" "$CLONE_DIR" || continue

    pushd "$CLONE_DIR" >/dev/null

    # if codeowners file already exists, skip everything
    if [ -f "CODEOWNERS" ]; then
        echo "✅ CODEOWNERS file already exists in $REPO, skipping."
        popd >/dev/null
        rm -rf "$CLONE_DIR"
        continue
    fi

    git checkout -b "$BRANCH_NAME"
    cp "../$CODEOWNERS_FILE" CODEOWNERS

    git add CODEOWNERS
    git commit -m "$COMMIT_MSG"
    git push --set-upstream origin "$BRANCH_NAME"

    gh pr create --title "$PR_TITLE" --body "$PR_BODY" --base develop --head "$BRANCH_NAME"

    popd >/dev/null
    rm -rf "$CLONE_DIR"

    echo "✅ Done with $REPO"

done < "$REPOS_FILE"
