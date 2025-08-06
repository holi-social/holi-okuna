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

  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  # keep this property as false. Having it true caused https://holi.atlassian.net/wiki/spaces/HOLI/pages/348258312/2023-06-27+All+services+down
  disable_dependent_services = false
  disable_on_destroy         = false
}

resource "google_sql_database" "database" {
  name     = random_id.main.hex
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  instance = local.environment_name == "production" ? data.terraform_remote_state.holi_infra_state.outputs.database_name_production : data.terraform_remote_state.holi_infra_state.outputs.database_name_development
}

output "database_name" {
  value = google_sql_database.database.name
}

# in CI, this is set via scripts/create-or-update-env.sh 
variable "image_tag" {
  type     = string
  nullable = false
}

### MIGRATION start
# In order to keep container startup time to a minimum, we perform migration steps in a job running before the deployment.
# This way, migrations are not executed on scaling up container count.
# We are using cloud run jobs for running the migration. We are using the same container, but a different entrypoint
# This alternative entrypoint script is added to the container in the Dockerfile.
# The job deployed by this resource is then triggered using the following null_resource definition every time a new image
# will be deployed.
resource "google_cloud_run_v2_job" "okuna_migration" {
  project             = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name                = "${random_id.main.hex}-migration"
  location            = local.default_region # finland, low CO2 emissions
  deletion_protection = false

  template {
    task_count = 1
    template {
      max_retries     = 1
      service_account = data.terraform_remote_state.holi_okuna_common_state.outputs.cloud_run_service_account_email
      containers {
        image   = "${data.terraform_remote_state.holi_infra_state.outputs.artifact_registry_location}/holi-okuna:${var.image_tag}"
        command = ["/migration-entrypoint.sh"]
        env {
          name  = "GOOGLE_CLOUD_PROJECT_ID"
          value = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
        }
        env {
          name  = "ENVIRONMENT"
          value = local.environment
        }
        env {
          name  = "ENVIRONMENT_ID"
          value = local.environment_name
        }
        env {
          name = "SECRET_KEY"
          value_source {
            secret_key_ref {
              version = "latest"
              secret  = local.environment_name == "production" ? "OKUNA_SECRET_KEY_PRODUCTION" : "OKUNA_SECRET_KEY_DEVELOPMENT"
            }
          }
        }
        env {
          name  = "ALLOWED_HOSTS"
          # there won't be any connections to the migration service hopefully
          value = "127.0.0.1,localhost"
        }
        env {
          name  = "RDS_DB_NAME"
          value = random_id.main.hex
        }
        env {
          name = "RDS_USERNAME"
          value_source {
            secret_key_ref {
              version = "latest"
              secret  = local.environment_name == "production" ? "OKUNA_DB_USERNAME_PRODUCTION" : "OKUNA_DB_USERNAME_DEVELOPMENT"
            }
          }
        }
        env {
          name = "RDS_PASSWORD"
          value_source {
            secret_key_ref {
              version = "latest"
              secret  = local.environment_name == "production" ? "OKUNA_DB_PASSWORD_PRODUCTION" : "OKUNA_DB_PASSWORD_DEVELOPMENT"
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
          value = data.terraform_remote_state.holi_infra_state.outputs.redis_host_cmek_development
        }
        env {
          name  = "REDIS_PORT"
          value = data.terraform_remote_state.holi_infra_state.outputs.redis_port_cmek_development
        }
        env {
          name = "REDIS_PASSWORD"
          value_source {
            secret_key_ref {
              version = "latest"
              secret  = "REDIS_CMEK_PASSWORD"
            }
          }
        }
        env {
          name  = "POSTHOG_HOST"
          value = local.posthog_host
        }
        env {
          name = "POSTHOG_API_KEY"
          value_source {
            secret_key_ref {
              secret  = local.environment_name == "production" ? "POSTHOG_API_KEY_PRODUCTION" : "POSTHOG_API_KEY_DEVELOPMENT"
              version = "latest"
            }
          }
        }
        env {
          name  = "SENTRY_DSN"
          value = "https://41084c0584d04b38a27d49fab9591b42@o949544.ingest.sentry.io/6421964"
        }
        env {
          name  = "IMAGEKIT_URL"
          value = "https://ik.imagekit.io/holi"
        }
        env {
          name  = "IMAGEKIT_PREFIX"
          value = local.environment_name == "production" ? "" : "_DEV_/"
        }
        env {
          name = "IMAGEKIT_PUBLIC_KEY"
          value_source {
            secret_key_ref {
              version = "latest"
              secret  = "OKUNA_IMAGEKIT_PUBLIC_KEY_PRODUCTION"
            }
          }
        }
        env {
          name = "IMAGEKIT_PRIVATE_KEY"
          value_source {
            secret_key_ref {
              version = "latest"
              secret  = "OKUNA_IMAGEKIT_PRIVATE_KEY_PRODUCTION"
            }
          }
        }
        resources {
          limits = {
            cpu    = 1
            memory = "1024Mi" # 512Mi is too little when applying all migrations
          }
        }
      }
      vpc_access {
        connector = data.terraform_remote_state.holi_infra_state.outputs.vpc_access_connector_id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }
  }

  depends_on = [google_project_service.service]
}

# This null resource triggers running the job every time the image tag changes, e.g. on every deployment, and waits for completion.
# It uses the gloud command to start the job, because terraform can't start it and could probably not wait for it.
resource "null_resource" "migrate" {
  triggers = {
    "image_tag" = var.image_tag
    # maybe add more trigger values for also redeploying on changes to the cloud run definition outside of image redeployments
  }

  provisioner "local-exec" {
    command = "gcloud --project=${data.terraform_remote_state.holi_infra_state.outputs.shared_project_id} run jobs execute ${google_cloud_run_v2_job.okuna_migration.name} --wait --region=${local.default_region}"
  }

}
### MIGRATION end

resource "google_cloud_run_service" "okuna" {
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name     = random_id.main.hex
  location = local.default_region # finland, low CO2 emissions
  # https://github.com/hashicorp/terraform-provider-google/issues/5898
  autogenerate_revision_name = true

  template {
    spec {
      service_account_name = data.terraform_remote_state.holi_okuna_common_state.outputs.cloud_run_service_account_email
      containers {
        image = "${data.terraform_remote_state.holi_infra_state.outputs.artifact_registry_location}/holi-okuna:${var.image_tag}"
        ports {
          container_port = 80
        }
        env {
          name  = "GOOGLE_CLOUD_PROJECT_ID"
          value = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
        }
        env {
          name  = "ENVIRONMENT"
          value = local.environment
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
          name  = "ALLOWED_HOSTS"
          # localhost for healthcheck (startup and liveness probes)
          # .run.app to allow its own cloudrun host to deliver pubsub message to the http pubsub reciever
          value = "${local.dns_name},.run.app,127.0.0.1,localhost"
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
              name = local.environment_name == "production" ? "OKUNA_DB_USERNAME_PRODUCTION" : "OKUNA_DB_USERNAME_DEVELOPMENT"
            }
          }
        }
        env {
          name = "RDS_PASSWORD"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = local.environment_name == "production" ? "OKUNA_DB_PASSWORD_PRODUCTION" : "OKUNA_DB_PASSWORD_DEVELOPMENT"
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
          value = data.terraform_remote_state.holi_infra_state.outputs.redis_host_cmek_development
        }
        env {
          name  = "REDIS_PORT"
          value = data.terraform_remote_state.holi_infra_state.outputs.redis_port_cmek_development
        }
        env {
          name = "REDIS_PASSWORD"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = "REDIS_CMEK_PASSWORD"
            }
          }
        }
        env {
          name  = "POSTHOG_HOST"
          value = local.posthog_host
        }
        env {
          name = "POSTHOG_API_KEY"
          value_from {
            secret_key_ref {
              name = local.environment_name == "production" ? "POSTHOG_API_KEY_PRODUCTION" : "POSTHOG_API_KEY_DEVELOPMENT"
              key  = "latest"
            }
          }
        }
        env {
          name  = "SENTRY_DSN"
          value = "https://41084c0584d04b38a27d49fab9591b42@o949544.ingest.sentry.io/6421964"
        }
        env {
          name  = "IMAGEKIT_URL"
          value = "https://ik.imagekit.io/holi"
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
          name  = "EMAIL_HOST"
          value = "smtp.gmail.com"
        }
        env {
          name  = "DEFAULT_FROM_EMAIL"
          value = "no-reply@holi.social"
        }
        env {
          name  = "SERVICE_EMAIL_ADDRESS"
          value = "no-reply@holi.social"
        }
        env {
          name  = "SERVER_EMAIL"
          value = "no-reply@holi.social"
        }
        env {
          name = "EMAIL_HOST_USER"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = "EMAIL_HOST_USER"
            }
          }
        }
        env {
          name = "EMAIL_HOST_PASSWORD"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = "EMAIL_HOST_PASSWORD"
            }
          }
        }
        env {
          name  = "ORY_BASE_URL"
          value = local.environment == "production" ? "https://auth.holi.social" : "https://dev-auth.holi.social"
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
        env {
          name  = "ORY_SESSION_EXPIRY_IN_H"
          value = local.environment_name == "production" ? "2160" : "600"
        }
        env {
          name  = "NOVU_API_URL"
          value = "https://eu.api.novu.co"
        }
        env {
          name = "NOVU_API_KEY"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = local.environment_name == "production" ? "NOVU_API_KEY_PRODUCTION" : "NOVU_API_KEY_DEVELOPMENT"
            }
          }
        }
        env {
          name  = "CHAT_SERVER_NAME"
          value = local.environment == "production" ? "holi.social" : "development-chat.holi.social"
        }
        env {
          name  = "CHAT_SERVER_URL"
          value = local.environment == "production" ? "https://chat.holi.social" : "https://development-chat.holi.social"
        }
        env {
          name = "CHAT_ADMIN_ACCESS_TOKEN"
          value_from {
            secret_key_ref {
              key  = "latest"
              name = local.environment_name == "production" ? "CHAT_ADMIN_ACCESS_TOKEN_PRODUCTION" : "CHAT_ADMIN_ACCESS_TOKEN_DEVELOPMENT"
            }
          }
        }
        env {
          name = "APPCUES_API_KEY"
          value_from {
            secret_key_ref {
              name = local.environment_name == "production" ? "APPCUES_API_KEY_PRODUCTION" : "APPCUES_API_KEY_DEVELOPMENT"
              key  = "latest"
            }
          }
        }
        env {
          name = "APPCUES_API_SECRET"
          value_from {
            secret_key_ref {
              name = local.environment_name == "production" ? "APPCUES_API_SECRET_PRODUCTION" : "APPCUES_API_SECRET_DEVELOPMENT"
              key  = "latest"
            }
          }
        }
        env {
          name = "APPCUES_ACCOUNT_ID"
          value_from {
            secret_key_ref {
              name = local.environment_name == "production" ? "APPCUES_ACCOUNT_ID_PRODUCTION" : "APPCUES_ACCOUNT_ID_DEVELOPMENT"
              key  = "latest"
            }
          }
        }

        startup_probe {
          initial_delay_seconds = 10
          period_seconds        = 5
          timeout_seconds       = 5
          failure_threshold     = 10
          http_get {
            path = "/graphql?query=%7B__typename%7D"
          }
        }

        liveness_probe {
          period_seconds    = 15
          timeout_seconds   = 10
          failure_threshold = 3
          http_get {
            path = "/graphql?query=%7B__typename%7D"
          }
        }

        resources {
          limits = {
            # cpu can only be scaled down to 1000m as long as container_concurrency is set to != 1
            cpu    = local.environment == "production" ? "4000m" : "4000m"
            memory = local.environment == "production" ? "2048Mi" : "2048Mi"
          }
          requests = {
            cpu    = local.environment == "production" ? "2000m" : "2000m"
            memory = local.environment == "production" ? "2048Mi" : "2048Mi"
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
        "autoscaling.knative.dev/maxScale" = local.environment == "production" ? "50" : "10"
        # Use the VPC Connector
        "run.googleapis.com/vpc-access-connector" = data.terraform_remote_state.holi_infra_state.outputs.vpc_access_connector_name
        # possible values: all-traffic/private-ranges-only(default) https://cloud.google.com/sdk/gcloud/reference/run/services/update#--vpc-egress
        "run.googleapis.com/vpc-access-egress" = "private-ranges-only"
        "run.googleapis.com/startup-cpu-boost" = "true"
      }
      # labels set on the revision level
      labels = {
        "environment_type" = local.environment_type
        "holi_service"     = "okuna"
      }
    }
  }

  # only accept traffic from the internal network, not from the internet
  metadata {
    annotations = {
      # possible values: all/internal/internal-and-cloud-load-balancing https://cloud.google.com/sdk/gcloud/reference/run/services/update#--ingress
      "run.googleapis.com/ingress" = "internal"
    }
    # labels set on the service level
    labels = {
      "environment_type" = local.environment_type
      "holi_service"     = "okuna"
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.service, null_resource.migrate]
}

resource "google_cloud_run_domain_mapping" "holi_social_okuna" {
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
