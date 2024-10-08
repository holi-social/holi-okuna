#!/usr/bin/env sh

# exit when any command fails
set -ex

# enable debug output in terraform
export TF_LOG=DEBUG

# retry logic for destroy: sometimes, a full workspace destroy does not work. This can be due to e.g.:
# * implicit dependencies between terraform resources not declared with depends_on,
# * unclean shutdown of resources, e.g. service does not close db connections, db still sees clients connected,
# * GCP stuff not allowing our resources to be deleted.
# Most of the time, retrying a destroy fixes these causes.
retry() {
  for i in $(seq 1 3); do
    set +e
    "$@"
    retval=$?
    set -e
    if [ "$retval" -ne "0" ]; then
      if [ "$i" -lt "3" ]; then
        echo "command '$*' failed in try $i, retrying after 60 seconds"
        sleep 60 # let things settle a bit
      else
        echo "command '$*' failed in try $i, giving up"
        exit $retval
      fi
    else
      break # success
    fi
  done
}

cd "$(dirname "$0")"/..

TF_LOG_PATH=terraform-init.log       terraform init
TF_LOG_PATH=terraform-version.log    terraform version
TF_LOG_PATH=terraform-workspace.log  terraform workspace select -or-create=true "$1"
TF_LOG_PATH=terraform-destroy.log    retry terraform destroy -auto-approve -var="image_tag=dummy"
TF_LOG_PATH=terraform-ws-default.log terraform workspace select default
TF_LOG_PATH=terraform-ws-delete.log  terraform workspace delete "$1"
