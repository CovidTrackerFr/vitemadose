remote_state {
  backend = "swift"
  config  = {
    container = "vmd-tfstate"
    state_name = "${path_relative_to_include()}.tfstate"

    auth_url = get_env("OS_AUTH_URL")
    tenant_id = get_env("OS_TENANT_ID")
    tenant_name = get_env("OS_TENANT_NAME")
    user_name = get_env("OS_USERNAME")
    password = get_env("OS_PASSWORD")
    region_name = "GRA"
  }
}

inputs = {
  nb_instances = 1
  ovh_region = path_relative_to_include()
  gitlab_runner_token = get_env("GITLAB_RUNNER_TOKEN")
}
