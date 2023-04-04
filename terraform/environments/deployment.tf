/**
 * The resource ids of resources must be unique. Since we might create resources for a branch multiple times
 * (after destroying the ones created before maybe failed, e.g. on environment cleanup, reopening a branch), we ensure uniqueness
 * by appending some random data to resource ids in order to avoid collisions.
 */
resource "random_id" "main" {
  byte_length = 2
  prefix      = "okuna-${local.environment_name}-"
}

resource "google_project_service" "service" {
  for_each = toset([
    "run.googleapis.com",
    "servicemanagement.googleapis.com",
    "servicecontrol.googleapis.com",
    "endpoints.googleapis.com",
  ])

  service = each.key

  project            = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  disable_on_destroy = false
}

resource "google_sql_database" "database" {
  name     = random_id.main.hex
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  instance = local.environment_name == "production" ? data.terraform_remote_state.holi_infra_state.outputs.database_name_production : data.terraform_remote_state.holi_infra_state.outputs.database_name_development
}

# in CI, this is set via scripts/create-or-update-env.sh
variable "image_tag" {
  type     = string
  nullable = false
}

resource "google_cloud_run_service" "okuna" {
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name     = random_id.main.hex
  location = "europe-north1" # finland, low CO2 emissions
  # https://github.com/hashicorp/terraform-provider-google/issues/5898
  autogenerate_revision_name = true

  template {
    spec {
      service_account_name = data.terraform_remote_state.holi_okuna_common_state.outputs.cloud_run_service_account_email
      containers {
        image = "${data.terraform_remote_state.holi_infra_state.outputs.gcr_location}/holi-okuna:${var.image_tag}"
        ports {
          container_port = 80
        }
        env {
          name  = "GOOGLE_CLOUD_PROJECT_ID"
          value = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
        }
        env {
          name  = "ENVIRONMENT"
          value = "production"
        }
        env {
          name  = "ENVIRONMENT_ID"
          value = local.environment_name
        }
        env {
          name = "SECRET_KEY"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = local.environment_name == "production" ? "OKUNA_SECRET_KEY_PRODUCTION" : "OKUNA_SECRET_KEY_DEVELOPMENT"
            }
          }
        }
        env {
          name = "ALLOWED_HOSTS"
          # TODO This could break the admin interface, we need to check it after deployment
          value = local.dns_name
        }
        env {
          name  = "RDS_DB_NAME"
          value = random_id.main.hex
        }
        env {
          name = "RDS_USERNAME"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = local.environment_name == "production" ? "OKUNA_POSTGRES_USERNAME_PRODUCTION" : "OKUNA_POSTGRES_USERNAME_DEVELOPMENT"
            }
          }
        }
        env {
          name = "RDS_PASSWORD"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = local.environment_name == "production" ? "OKUNA_POSTGRES_PASSWORD_PRODUCTION" : "OKUNA_POSTGRES_PASSWORD_DEVELOPMENT"
            }
          }
        }
        env {
          name  = "RDS_PORT"
          value = "5432"
        }
        env {
          name  = "RDS_HOSTNAME"
          value = local.environment_name == "production" ? data.terraform_remote_state.holi_infra_state.outputs.database_ip_address_production : data.terraform_remote_state.holi_infra_state.outputs.database_ip_address_development
        }
        env {
          name  = "REDIS_HOST"
          value = data.terraform_remote_state.holi_infra_state.outputs.redis_host_development
        }
        env {
          name  = "REDIS_PORT"
          value = data.terraform_remote_state.holi_infra_state.outputs.redis_port_development
        }
        env {
          name  = "REDIS_PASSWORD"
          value = data.terraform_remote_state.holi_infra_state.outputs.redis_password_development
        }
        env {
          name  = "SENTRY_DSN"
          value = "https://41084c0584d04b38a27d49fab9591b42@o949544.ingest.sentry.io/6421964"
        }
        env {
          name  = "IMAGEKIT_URL"
          value = local.environment_name == "https://ik.imagekit.io/holi"
        }
        env {
          name  = "IMAGEKIT_PREFIX"
          value = local.environment_name == "production" ? "" : "_DEV_/"
        }
        env {
          name = "IMAGEKIT_PUBLIC_KEY"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = "OKUNA_IMAGEKIT_PUBLIC_KEY_PRODUCTION"
            }
          }
        }
        env {
          name = "IMAGEKIT_PRIVATE_KEY"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = "OKUNA_IMAGEKIT_PRIVATE_KEY_PRODUCTION"
            }
          }
        }
        env {
          name  = "ORY_BASE_URL"
          value = local.environment == "production" ? "https://auth.project-holi.org" : "https://dev-auth.project-holi.org"
        }
        env {
          name = "ORY_ACCESS_TOKEN"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = local.environment_name == "production" ? "ORY_ACCESS_TOKEN_PRODUCTION" : "ORY_ACCESS_TOKEN_DEVELOPMENT"
            }
          }
        }
        resources {
          limits = {
            # cpu can only be scaled down to 1000m as long as container_concurrency is set to != 1
            cpu    = local.environment == "production" ? "1000m" : "1000m"
            memory = local.environment == "production" ? "1024Mi" : "768Mi"
          }
          requests = {
            cpu    = local.environment == "production" ? "1000m" : "10m"
            memory = local.environment == "production" ? "1024Mi" : "512Mi"
          }
        }
      }
      container_concurrency = 0 # 0 means thread safe, no restriction on max concurrency
      timeout_seconds       = 300
    }
    # template annotations: https://cloud.google.com/run/docs/reference/rpc/google.cloud.run.v1#revisiontemplate
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = local.environment == "production" ? "1" : "0"
        "autoscaling.knative.dev/maxScale" = local.environment == "production" ? "50" : "5"
        # Use the VPC Connector
        "run.googleapis.com/vpc-access-connector" = data.terraform_remote_state.holi_infra_state.outputs.vpc_access_connector_name
        # possible values: all-traffic/private-ranges-only(default) https://cloud.google.com/sdk/gcloud/reference/run/services/update#--vpc-egress
        "run.googleapis.com/vpc-access-egress" = "private-ranges-only"
      }
    }
  }

  # only accept traffic from the internal network, not from the internet
  metadata {
    annotations = {
      # possible values: all/internal/internal-and-cloud-load-balancing https://cloud.google.com/sdk/gcloud/reference/run/services/update#--ingress
      "run.googleapis.com/ingress" = "internal"
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.service]
}

resource "google_cloud_run_domain_mapping" "okuna" {
  project = google_cloud_run_service.okuna.project
  # location needs to be the same as the service's
  location = google_cloud_run_service.okuna.location
  name     = local.dns_name

  metadata {
    namespace = google_cloud_run_service.okuna.project
  }

  spec {
    route_name = google_cloud_run_service.okuna.name
  }
}

# TODO security: Can we restrict this to a specific service account (of the API proxy) some day?
data "google_iam_policy" "okuna" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_service_iam_policy" "okuna" {
  location = google_cloud_run_service.okuna.location
  project  = google_cloud_run_service.okuna.project
  service  = google_cloud_run_service.okuna.name

  policy_data = data.google_iam_policy.okuna.policy_data
}
