---
name: github-actions-ci-debugging
description: Diagnose GitHub Actions failures, permission errors, skipped jobs, artifact problems, Android APK builds and deployment logs using the exact workflow run and commit.
---
# GitHub Actions CI Debugging

1. Identify the exact repository, branch, workflow run ID, attempt and commit SHA.
2. Fetch run summary, jobs, step conclusions and logs for the latest attempt.
3. Find the first failing step; later skipped steps may be consequences.
4. Classify the failure: code/test, dependency, runner/toolchain, permissions, environment protection, artifact, cache or deployment.
5. Check workflow permissions and action inputs. Grant least privilege only.
6. For artifacts, verify name, path, size, retention and contents. Validate APK structure before sharing.
7. Reproduce code failures in a focused test or workflow job.
8. Add regression tests for code defects and workflow checks for configuration defects.
9. Re-run only failed jobs when safe; regenerate upstream artifacts when necessary.
10. Verify the final run against the intended commit SHA.

Report successful, failed, skipped, cancelled and in-progress jobs separately. Never infer success from an earlier run or successful artifact upload.
