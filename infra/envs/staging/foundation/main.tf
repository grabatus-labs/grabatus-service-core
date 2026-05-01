# Root module for the dev environment's foundation stack.
#
# This file is intentionally empty until Plan 2D / CP6 wires the WIF,
# Artifact Registry, shared receiver, and alerts modules.
#
# Until then, terraform validate must still pass — the file exists so
# that `terraform init -backend=false && terraform validate` from this
# directory exits 0 and the CI workflow can rely on it.
