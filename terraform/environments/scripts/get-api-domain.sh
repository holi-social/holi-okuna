#!/usr/bin/env sh

# exit when any command fails
set -ex

cd terraform/environments > /dev/null

terraform output -raw api_domain
