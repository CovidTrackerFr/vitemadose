terraform {
  source = "../../modules/runner"
}

include {
  path = find_in_parent_folders()
}

inputs = {
  nb_instances = 0
}
