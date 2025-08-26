locals {
  # predefined environment names are staging, production, and <branchname>
  environment      = terraform.workspace
  environment_name = trim(substr(local.environment, 0, 22), ".-") # limits the length of the name that it fits constraints google imposes for some resources, e.g. project ids
  environment_type = contains(["staging", "production"], local.environment) ? local.environment : "review"

  # the dns name can be at most 64 chars in total
  dns_name = "${trimsuffix(substr(local.environment, 0, 34), ".-")}.${data.terraform_remote_state.holi_okuna_common_state.outputs.dns_okuna_domain}"

  default_region = data.terraform_remote_state.holi_infra_state.outputs.default_region

  posthog_host = "https://eu.posthog.com"

  project_id = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id

  external_data_topic_name = local.environment_name == "production" ? data.terraform_remote_state.holi_data_pipeline_common_state.outputs.google_pubsub_topic_external_data_production_name : data.terraform_remote_state.holi_data_pipeline_common_state.outputs.google_pubsub_topic_external_data_staging_name

  external_data_topic_id = local.environment_name == "production" ? data.terraform_remote_state.holi_data_pipeline_common_state.outputs.google_pubsub_topic_external_data_production : data.terraform_remote_state.holi_data_pipeline_common_state.outputs.google_pubsub_topic_external_data_staging

}
