#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# needs to start with https:// for this script to work, of course
url="$1"

# google has a cdn answering on requests. This cdn takes a while to be fully updated.
# Therefore, we don't return on first success, but on a number of consecutive successes.
number_of_consecutive_successful_tries_needed=25
number_of_consecutive_successful_tries_achieved=0

[ -z "$url" ] && echo "missing url as first param" && exit 1

echo -n "Checking if SSL certificate for $url is installed: "

# storage for the return value of the curl command
retval=0

# early break on success (no need to wait on existing deployments)
set +e
curl -sSLIm 10 "$url" > /dev/null 2>& 1 
retval=$?
set -e
if [ $retval -eq 0 ]; then
  echo "success on first try, not checking further"
  exit 0
fi


# shellcheck disable=SC2034
for i in {1..2500}; do
  set +e
  out=$(curl -sSLIm 10 "$url" 2>& 1)
  retval=$?
  set -e
  # shellcheck disable=SC2181
  if [ $retval == 0 ]; then
    number_of_consecutive_successful_tries_achieved=$((number_of_consecutive_successful_tries_achieved + 1))
    echo "success (${number_of_consecutive_successful_tries_achieved})"
    if [ "$number_of_consecutive_successful_tries_achieved" -eq "$number_of_consecutive_successful_tries_needed" ]; then
      echo "test successful after $i total tries"
      exit 0
    fi
    sleep 1
  else
    echo -n "."
    number_of_consecutive_successful_tries_achieved=0
    sleep 1
  fi
done

echo -e "no success after $i tries. Last output was:\n$out"
exit 1
