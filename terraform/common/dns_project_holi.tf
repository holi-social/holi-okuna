
locals {
  # effectively, this is social.apis.project-holi.org
  project_holi_okuna_environments_zone_dns_name = "social.${data.terraform_remote_state.holi_infra_state.outputs.dns_project_holi_apis_zone_domain}."
}

# okuna environments zone
resource "google_dns_managed_zone" "project_holi_okuna_environments_zone" {
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name     = "okuna-environments-zone"
  dns_name = local.project_holi_okuna_environments_zone_dns_name
}

resource "google_dns_record_set" "project_holi_okuna_environments_zone_entry" {
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name    = local.project_holi_okuna_environments_zone_dns_name
  type    = "NS"
  ttl     = 300

  managed_zone = data.terraform_remote_state.holi_infra_state.outputs.dns_project_holi_apis_zone_name

  rrdatas = google_dns_managed_zone.project_holi_okuna_environments_zone.name_servers
}

output "dns_project_holi_okuna_domain" {
  value = trim(google_dns_managed_zone.project_holi_okuna_environments_zone.dns_name, ".")
}

output "dns_project_holi_okuna_domain_name" {
  value = google_dns_managed_zone.project_holi_okuna_environments_zone.name
}