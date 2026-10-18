# Free Render deployment

The root `render.yaml` defines a free Docker web service for the API and a
free static site for the React frontend. The static site claims
`quranicshazam.tahachelly.com` and calls the API at
`quranic-shazam-api.onrender.com`. The Docker build downloads the versioned
ONNX release asset and verifies its SHA-256; the model is not stored in Git.

To create the services, sign in to Render, choose **New > Blueprint**, connect
`taha3313/quranic-shazam`, and apply the blueprint from `main`. Render then
builds both services from the pushed repository. In the static site's custom
domain settings, Render shows the DNS target for `quranicshazam.tahachelly.com`.
Add the CNAME record in Cloudflare, then verify the domain in Render. Render
issues and renews HTTPS certificates for free custom domains.

The free web service has 512 MB RAM and 0.1 CPU. It sleeps after 15 minutes
without traffic, takes about a minute to wake, and shares 750 free instance
hours per month across the workspace. It can restart at any time and has no
persistent disk. The app keeps its model files in the image, so recognition
data does not depend on a persistent disk. Free hosting is suitable for a
low-traffic demo; the ayah recognizer will be substantially slower on 0.1 CPU
than the one-CPU validation run. Render describes free instances as intended
for previews and hobby projects rather than production.

## CI-gated automatic deployment

The preferred configuration is native Render auto-deploy with
`autoDeployTrigger: checksPass` on both services. Keep both GitHub Actions jobs
enabled: **Backend tests** and **Frontend checks**. A frontend-only change should
deploy the site; the API's `backend` root directory excludes that change.

When diagnosing missing deploys, check each service's **Settings > Build &
Deploy** for the Git credentials, repository, branch, root directory, build
filters, and **After CI Checks Pass** setting. In GitHub's Render app installation,
confirm repository access includes `taha3313/quranic-shazam`. In the Blueprint
`exs-dbacce5g1s2s73bj6t7g`, confirm its repository, `main` branch, `render.yaml`
path, and Auto Sync setting. A public repository URL alone does not establish a
connected Git provider. Auto Sync and service auto-deploy are separate settings.

### CI deploy-hook workflow

The `render-deploy` job in `.github/workflows/ci.yml` depends on both CI jobs,
runs only for pushes to `main`, and requests the exact tested SHA. It filters
changes by service directory; changes to `render.yaml` deploy both services.
Pull requests and workflow dispatches cannot invoke it. The repository variable
`RENDER_DEPLOY_HOOKS_ENABLED` is enabled and both service hook URLs are stored
as encrypted Actions secrets. The Blueprint sets both services'
`autoDeployTrigger` to `off`, preventing duplicate native triggers and keeping
the free service plans unchanged. Both CI jobs remain required for the deploy
job. A hook job succeeding proves acceptance or queueing only; independently
confirm the matching Render SHA reaches `live` and verify the public site with a
cache-bypassing request.

The script never logs the hook URL or response body and does not retry ambiguous
network failures, which could otherwise create duplicate deployments. If a
request fails, inspect Render before rerunning the workflow. An API/hook trigger
is evidence of automation only when correlated with the GitHub deployment job;
an agent-triggered API deployment is not native auto-deploy proof.

To return to native integration, first disable `RENDER_DEPLOY_HOOKS_ENABLED`,
then restore `checksPass` in the Blueprint and service settings and verify a new
push. None of these steps require changing the free API plan or static hosting.

References: [Render deploys](https://render.com/docs/deploys),
[Git provider setup](https://render.com/docs/git-provider),
[monorepo filters](https://render.com/docs/monorepo-support), and
[deploy hooks](https://render.com/docs/deploy-hooks).

### Investigation on 2026-10-18 (UTC)

- Pushed frontend-only commit `1090d8a590f07e1c522e26497b7dbbdbc0beaf8d`
  at 17:19:43, adding an author metadata tag for verification.
- GitHub Actions run `39149065284`: Frontend checks passed at 17:20:01;
  Backend tests passed at 17:20:07.
- Observed Render independently until after 17:30:07 (ten minutes after CI).
  No new frontend deployment appeared. The latest record remained
  `dep-dbafsb61egvs73ai9rl0`, the earlier API-triggered deploy of `6a06ed6`.
  No deployment was manually triggered during this verification.
- Render event queries during the window returned no events, including no
  `commit_ignored` evidence. A public-site cache-bypass request returned HTTP 200
  without the verification metadata.
- Both services still reported `autoDeploy=yes`, `autoDeployTrigger=checksPass`,
  correct repository, branch, and root directories. The backend plan was free.
- Repository webhook listing was empty, which does not establish absence of a
  Render GitHub App integration. Available GitHub authentication could not read
  app-installation details. The Render connector lacked source-credential,
  Blueprint-settings, delivery-log, and deploy-hook retrieval operations.
- Cause remains unconfirmed. Public-URL source connection, Git credential/app
  access, and push/check delivery remain hypotheses. Current Blueprint Auto Sync
  and provider-side build filters could not be independently inspected.
- The GitHub Actions deploy-hook path was activated after the Render dashboard
  confirmed the linked repo, branch, roots, and empty build filters. Both hook
  secrets were stored through GitHub's encrypted Actions secrets API; their
  values are intentionally omitted. The Blueprint now declares native auto-
  deploy off, leaving CI-gated GitHub Actions as the deployment authority.
- A fresh push is required to prove the configured workflow deploys the matching
  SHA and that it becomes live. Activation alone is not deployment proof.
