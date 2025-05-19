#!/bin/sh
# notify-slack.sh - Script to send release notifications to Slack
# Usage: ./notify-slack.sh [options]
#
# Options:
#   -w, --webhook URL       Slack webhook URL (required)
#   -m, --message TEXT      Custom message text (required)
#   -h, --help              Show this help message

# Function to display usage information
show_help() {
    grep '^#' "$0" | grep -v '#!/bin/sh' | sed 's/^# //; s/^#//'
    exit 0
}

# Function to display error message and exit
error() {
    echo "ERROR: $1" >&2
    exit 1
}

# Initialize values
WEBHOOK=""
MESSAGE=""

# Parse command-line arguments
while [ $# -gt 0 ]; do
    case "$1" in
        -w|--webhook)
            WEBHOOK="$2"
            shift 2
            ;;
        -m|--message)
            MESSAGE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Escape special characters in strings for JSON
escape_json() {
    printf '%s\n' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/$/\\n/; s/\r/\\r/g; s/\t/\\t/g' | tr -d '\n' | sed 's/\\n$//'
}

# Strip leading whitespace
strip_leading_whitespace() {
    printf '%s\n' "$1" | sed 's/^[[:space:]]*//'
}

# Validate required parameters
[ -z "$WEBHOOK" ] && error "Webhook URL is required. Use -w or --webhook to specify."
[ -z "$MESSAGE" ] && error "Message text is required. Use -m or --message to specify."

MESSAGE_STRIPPED=$(strip_leading_whitespace "$MESSAGE")
MESSAGE_ESCAPED=$(escape_json "$MESSAGE_STRIPPED")

curl -X POST -H "Content-Type: application/json" -s \
  --data "{\"username\": \"holi-okuna pipeline\", \"icon_url\": \"https://placehold.co/72x72/1a0015/white?text=okuna\", \"text\": \"$MESSAGE_ESCAPED\"}" \
  "$WEBHOOK" 1> /dev/null || echo "WARNING: Failed to send notification to Slack."