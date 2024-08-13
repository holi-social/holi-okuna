locals {
  # predefined environment names are staging, production, and <branchname>
  environment      = terraform.workspace
  environment_name = trim(substr(local.environment, 0, 22), ".-") # limits the length of the name that it fits constraints google imposes for some resources, e.g. project ids

  # the dns name can be at most 64 chars in total
  dns_name = "${trimsuffix(substr(local.environment, 0, 34), ".-")}.${data.terraform_remote_state.holi_okuna_common_state.outputs.dns_okuna_domain}"

  default_region = data.terraform_remote_state.holi_infra_state.outputs.default_region

  posthog_host     = "https://eu.posthog.com"
  posthog_api_key  = local.environment == "production" ? "phc_otDkhAWe558gCziFqIE3XrGla2AvdosZftmhOyjfWAu" : "phc_hjzX978CctzGvUBxYatJkyQDAg9c8ZZyreAXtPn6FJ6"
}
