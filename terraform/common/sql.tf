# -- user okuna (development) --
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

# -- user okuna (production) --

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

# -- user data-pipelines-readonly (development) --

data "google_secret_manager_secret_version_access" "okuna_data_pipelines_username_development" {
  secret  = "OKUNA_DB_DATA_PIPELINES_USERNAME_DEVELOPMENT"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

data "google_secret_manager_secret_version_access" "okuna_data_pipelines_password_development" {
  secret  = "OKUNA_DB_DATA_PIPELINES_PASSWORD_DEVELOPMENT"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

resource "google_sql_user" "okuna_data_pipelines_development" {
  name     = data.google_secret_manager_secret_version_access.okuna_data_pipelines_username_development.secret_data
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  instance = data.terraform_remote_state.holi_infra_state.outputs.database_name_development
  password = data.google_secret_manager_secret_version_access.okuna_data_pipelines_password_development.secret_data
}

# manually created permissions within okuna_staging
#\c okuna_staging;
#
#-- Grant CONNECT privilege on the database
#GRANT CONNECT ON DATABASE okuna-staging-4db7 TO "okuna-data-pipelines-readonly";
#
#-- Grant USAGE on the public schema (and any other schemas you need)
#GRANT USAGE ON SCHEMA public TO "okuna-data-pipelines-readonly";
#
#-- Grant SELECT on all existing tables
#GRANT SELECT ON ALL TABLES IN SCHEMA public TO "okuna-data-pipelines-readonly";
#
#-- Grant SELECT on all future tables (important for new tables)
#ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "okuna-data-pipelines-readonly";

data "google_secret_manager_secret_version_access" "okuna_data_pipelines_username_production" {
  secret  = "OKUNA_DB_DATA_PIPELINES_USERNAME_PRODUCTION"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

data "google_secret_manager_secret_version_access" "okuna_data_pipelines_password_production" {
  secret  = "OKUNA_DB_DATA_PIPELINES_PASSWORD_PRODUCTION"
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
}

resource "google_sql_user" "okuna_data_pipelines_production" {
  name     = data.google_secret_manager_secret_version_access.okuna_data_pipelines_username_production.secret_data
  project  = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  instance = data.terraform_remote_state.holi_infra_state.outputs.database_name_production
  password = data.google_secret_manager_secret_version_access.okuna_data_pipelines_password_production.secret_data
}

# manually created permissions within okuna_production
#\c okuna_production;
#
#-- Grant CONNECT privilege on the database
#GRANT CONNECT ON DATABASE okuna-production-deb5 TO "okuna-data-pipelines-readonly";
#
#-- Grant USAGE on the public schema (and any other schemas you need)
#GRANT USAGE ON SCHEMA public TO "okuna-data-pipelines-readonly";
#
#-- Grant SELECT on all existing tables
#GRANT SELECT ON ALL TABLES IN SCHEMA public TO "okuna-data-pipelines-readonly";
#
#-- Grant SELECT on all future tables (important for new tables)
#ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "okuna-data-pipelines-readonly";