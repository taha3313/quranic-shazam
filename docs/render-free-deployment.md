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
