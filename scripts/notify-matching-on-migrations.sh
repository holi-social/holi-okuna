#!/usr/bin/env sh

CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r $CI_COMMIT_SHA)
MIGRATION_CHANGED=false

for file in $CHANGED_FILES; do
  case "$file" in
    */migrations/*.py)
      MIGRATION_CHANGED=true
      break
      ;;
  esac
done

if [ "$MIGRATION_CHANGED" = "true" ]; then
  scripts/notify-slack.sh \
    --webhook "$SLACK_MATCHING_MON_DATA_PROD_WEBHOOK_URL" \
    --message "⚠️A migration was detected in holi-okuna! This is the commit containing the migration:
Author:  $CI_COMMIT_AUTHOR
Commit:  $CI_COMMIT_SHA
$CI_COMMIT_MESSAGE
---
See $CI_PIPELINE_URL for details"
fi