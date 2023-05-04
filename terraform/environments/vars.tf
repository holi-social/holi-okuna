locals {
  # predefined environment names are staging, production, and <branchname>
  environment      = terraform.workspace
  environment_name = trim(substr(local.environment, 0, 22), ".-") # limits the length of the name that it fits constraints google imposes for some resources, e.g. project ids

  # the dns name can be at most 64 chars in total
  dns_name = "${trimsuffix(substr(local.environment, 0, 34), ".-")}.${data.terraform_remote_state.holi_okuna_common_state.outputs.dns_okuna_domain}"
  project_holi_dns_name = "${trimsuffix(substr(local.environment, 0, 34), ".-")}.${data.terraform_remote_state.holi_okuna_common_state.outputs.dns_project_holi_okuna_domain}"
}
