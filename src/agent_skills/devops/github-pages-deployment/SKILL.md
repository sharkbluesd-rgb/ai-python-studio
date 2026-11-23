---
name: github-pages-deployment
description: Configure and troubleshoot GitHub Actions deployments to GitHub Pages, including permissions, environments, artifacts, project-site paths, and live-site verification.
---

# GitHub Pages Deployment

Use this skill for publishing a static web preview from GitHub Actions, especially project sites hosted at OWNER.github.io/REPOSITORY/.

## Deployment procedure

1. Inspect workflow triggers, jobs, dependencies, artifact names, and deploy action versions before editing.
2. Build the static site into one explicit output directory and verify it contains index.html plus all referenced assets.
3. Upload the Pages artifact using the supported Pages artifact action; ensure the artifact path is the exact build output directory.
4. Configure the deployment job with least-required permissions: pages: write and id-token: write. Keep checkout/build permissions separate where practical.
5. Use the Pages deployment environment consistently (normally github-pages). Do not try to create or mutate repository Pages settings from a workflow unless explicitly authorized.
6. Check environment deployment branch/tag rules. A protected environment can reject a valid workflow from a branch that is not allowlisted. Preserve existing allowed branches unless the owner explicitly requests a change.
7. Ensure deploy depends on successful artifact upload and references the exact artifact name. Avoid deploying stale or unrelated artifacts.
8. For project sites, configure framework base path and asset paths for /REPOSITORY/. Do not assume root-domain paths.
9. Inspect the workflow run summary and deployment URL. Make an HTTP request to the exact URL and verify the page and key assets.
10. After deployment, test a fresh browser session and a mobile browser. Check cache and service-worker behavior before concluding a previous error is fixed.

## Failure interpretation

- 404 at site root: verify Pages configuration, deployment status, repository visibility/plan constraints, and exact project-site URL.
- Resource not accessible by integration: inspect token permissions and whether workflow attempts an administrative Pages-setting operation.
- Environment branch not allowed: update the environment rule only with owner authorization; do not remove unrelated protection rules.
- Artifact upload succeeded but deploy skipped: inspect job dependencies, conditional expressions, artifact names, and deployment environment.
- Page loads but assets fail: inspect base path, generated URLs, and deployed artifact contents.

## Verification standard

A green build is not a green deployment. A green deployment is not proof the application runs. Record separately: build result, artifact upload result, deploy job result, published URL and HTTP response, and runtime smoke-test result.

Never claim a URL is live until the deployment job succeeds and the exact URL is checked. Do not deploy secrets or private source files to a public Pages site.
