#!/usr/bin/env sh

# exit when any command fails
set -ex

# enable debug output in terraform
export TF_LOG=DEBUG

cd terraform/environments

TF_LOG_PATH=terraform-init.log       terraform init
TF_LOG_PATH=terraform-version.log    terraform version
TF_LOG_PATH=terraform-workspace.log  terraform workspace new "$1" || terraform workspace select "$1"
TF_LOG_PATH=terraform-destroy.log    terraform destroy -auto-approve -var="image_tag=dummy"
TF_LOG_PATH=terraform-ws-default.log terraform workspace select default
TF_LOG_PATH=terraform-ws-delete.log  terraform workspace delete "$1"
