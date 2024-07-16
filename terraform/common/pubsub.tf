resource "google_project_service_identity" "pubsub_serviceaccount" {
  provider = google-beta

  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  service = "pubsub.googleapis.com"
}

resource "google_kms_crypto_key" "pubsub_okuna" {
  name     = "pubsub-key-okuna"
  key_ring = data.terraform_remote_state.holi_infra_state.outputs.kms_shared_key_ring_id

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_binding" "pubsub_okuna" {
  crypto_key_id = google_kms_crypto_key.pubsub_okuna.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  members = [
    "serviceAccount:${google_project_service_identity.pubsub_serviceaccount.email}",
  ]
}

resource "google_pubsub_topic" "okuna_staging" {
  project      = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name         = "okuna_staging"
  kms_key_name = google_kms_crypto_key.pubsub_okuna.id
  message_storage_policy {
    allowed_persistence_regions = [local.default_region]
  }
  depends_on = [google_kms_crypto_key_iam_binding.pubsub_okuna]
}

resource "google_pubsub_topic" "okuna_production" {
  project      = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name         = "okuna_production"
  kms_key_name = google_kms_crypto_key.pubsub_okuna.id
  message_storage_policy {
    allowed_persistence_regions = [local.default_region]
  }
}

output "google_pubsub_topic_okuna_staging" {
  value = google_pubsub_topic.okuna_staging.id
}

output "google_pubsub_topic_okuna_production" {
  value = google_pubsub_topic.okuna_production.id
}
