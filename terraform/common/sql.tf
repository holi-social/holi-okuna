data "google_secret_manager_secret_version_access" "okuna_db_username_development" {
  secret  = "OKUNA_DB_USERNAME_DEVELOPMENT"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

data "google_secret_manager_secret_version_access" "okuna_db_password_development" {
  secret  = "OKUNA_DB_PASSWORD_DEVELOPMENT"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

resource "google_sql_user" "okuna_development" {
  name     = data.google_secret_manager_secret_version_access.okuna_db_username_development.secret_data
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  instance = data.terraform_remote_state.holi_infra_state.outputs.database_name_development
  password = data.google_secret_manager_secret_version_access.okuna_db_password_development.secret_data
}

data "google_secret_manager_secret_version_access" "okuna_db_username_production" {
  secret  = "OKUNA_DB_USERNAME_PRODUCTION"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

data "google_secret_manager_secret_version_access" "okuna_db_password_production" {
  secret  = "OKUNA_DB_PASSWORD_PRODUCTION"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

resource "google_sql_user" "okuna_production" {
  name     = data.google_secret_manager_secret_version_access.okuna_db_username_production.secret_data
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  instance = data.terraform_remote_state.holi_infra_state.outputs.database_name_production
  password = data.google_secret_manager_secret_version_access.okuna_db_password_production.secret_data
}

