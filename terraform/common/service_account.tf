resource "google_service_account" "okuna" {
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  account_id   = "cloudrun-service-okuna"
  display_name = "Okuna service account for Cloud Run"
}

# TODO: needs permissions for accessing DB, Redis
# DB: https://cloud.google.com/sql/docs/postgres/iam-roles#roles maybe nothing needed, since we connect via IP
# REDIS

output "cloud_run_service_account_email" {
  value = google_service_account.okuna.email
}
