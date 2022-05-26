#!/usr/bin/env sh

# exit when any command fails
set -ex

# enable full debug output in terraform, which is only written to logfiles
export TF_LOG=TRACE

cd terraform/environments

WORKSPACE=$1
TAG=$2

TF_LOG_PATH=terraform-init.log terraform init
TF_LOG_PATH=terraform-version.log terraform version
TF_LOG_PATH=terraform-workspace.log terraform workspace new "$WORKSPACE" || terraform workspace select "$WORKSPACE"
TF_LOG_PATH=terraform-plan.log terraform plan -var="image_tag=$TAG" -out plan -no-color | tee tfplan.plain
TF_LOG_PATH=terraform-apply.log terraform apply -auto-approve -parallelism=50 plan