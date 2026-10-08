+++
id = "deliver-workflow-branch"
title = "Fixed `deliver.yml` to target `master`"
filed = 2026-08-04
closed = 2026-08-04
outcome = "shipped"
+++

Fixed `deliver.yml` to target `master` instead of `main`, since the repo's
default branch is `master` and the workflow was never triggering.
