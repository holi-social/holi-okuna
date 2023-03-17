resource "google_pubsub_topic" "okuna_development" {
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name = "okuna_development"
  message_storage_policy {
    allowed_persistence_regions = ["europe-north1"]
  }
}

resource "google_pubsub_topic" "okuna_production" {
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name = "okuna_production"
  message_storage_policy {
    allowed_persistence_regions = ["europe-north1"]
  }
}

output "google_pubsub_topic_okuna_development" {
  value = google_pubsub_topic.okuna_development.name
}

output "google_pubsub_topic_okuna_production" {
  value = google_pubsub_topic.okuna_production.name
}