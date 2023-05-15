resource "google_dns_record_set" "holi_social_okuna_domain_record_set" {
  project      = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  managed_zone = data.terraform_remote_state.holi_okuna_common_state.outputs.dns_okuna_domain_name
  name         = "${google_cloud_run_domain_mapping.holi_social_okuna.name}."
  type         = google_cloud_run_domain_mapping.holi_social_okuna.status[0].resource_records[0].type
  ttl          = 300
  rrdatas      = [google_cloud_run_domain_mapping.holi_social_okuna.status[0].resource_records[0].rrdata]
}

resource "google_dns_record_set" "okuna_domain_record_set" {
  project      = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  managed_zone = data.terraform_remote_state.holi_okuna_common_state.outputs.dns_project_holi_okuna_domain_name
  name         = "${google_cloud_run_domain_mapping.okuna.name}."
  type         = google_cloud_run_domain_mapping.okuna.status[0].resource_records[0].type
  ttl          = 300
  rrdatas      = [google_cloud_run_domain_mapping.okuna.status[0].resource_records[0].rrdata]
}

output "api_domain" {
  value       = trimsuffix(google_dns_record_set.okuna_domain_record_set.name, ".")
  description = "Domain where the api resides"
}
