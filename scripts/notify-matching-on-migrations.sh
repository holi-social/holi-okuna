#!/bin/sh
# Script to detect migrations in a build job execution in order to notify the Matching Team of changes to Okunas
# database schema.

# in case of a push of multiple commits, each commit might contain a migration
# therefore, comparison is between $CI_COMMIT_BEFORE_SHA (commit before push) and $CI_COMMIT_SHA (newest commit)
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r $CI_COMMIT_BEFORE_SHA $CI_COMMIT_SHA)
MIGRATION_DETECTED=false

for file in $CHANGED_FILES; do
  case "$file" in
    */migrations/*.py)
      echo "Migration detected in $file"
      MIGRATION_DETECTED=true
      break
      ;;
  esac
done

if [ "$MIGRATION_DETECTED" = "true" ]; then
  echo "Notifying Matching team via Slack monitoring channel"
  scripts/notify-slack.sh \
    --webhook "$SLACK_MATCHING_MON_DATA_PROD_WEBHOOK_URL" \
    --message "⚠️ A migration was detected in holi-okuna! This is the push containing the commit(s) with migration(s):

git log --oneline $CI_COMMIT_BEFORE_SHA^..$CI_COMMIT_SHA

---

See $CI_PIPELINE_URL for details"
fi