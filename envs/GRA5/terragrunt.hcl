terraform {
  source = "../../modules/runner"
}

include {
  path = find_in_parent_folders()
}
