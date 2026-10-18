"""Request a Render deploy without exposing the secret hook URL or response."""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    component = os.environ["COMPONENT"]
    if component not in {"frontend", "backend"}:
        raise SystemExit("Unknown deployment component")
    sha = os.environ["GITHUB_SHA"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit("Invalid tested commit SHA")
    before = os.environ["BEFORE_SHA"]
    if before != "0" * 40:
        # A missing base fails closed, rather than silently deploying untested HEAD.
        paths = (
            subprocess.check_output(
                ["git", "diff", "--name-only", "-z", before, sha],
            )
            .decode()
            .split("\0")
        )
        shared = {"render.yaml"}
        if not any(
            path.startswith(component + "/") or path in shared for path in paths
        ):
            print(f"No deployment changes for {component}")
            return

    hook = os.environ.get("RENDER_DEPLOY_HOOK_URL", "")
    parsed = urllib.parse.urlsplit(hook)
    expected_service = {
        "frontend": "srv-dbaccjrncjis73d1j9vg",
        "backend": "srv-dbaccjrncjis73d1ja00",
    }[component]
    if (
        parsed.scheme != "https"
        or parsed.netloc != "api.render.com"
        or parsed.path != "/deploy/" + expected_service
        or not urllib.parse.parse_qs(parsed.query).get("key")
    ):
        raise SystemExit(
            f"Missing or invalid Render deploy hook secret for {component}"
        )
    query = urllib.parse.parse_qs(parsed.query)
    query["ref"] = [sha]
    url = urllib.parse.urlunsplit(
        parsed._replace(query=urllib.parse.urlencode(query, doseq=True))
    )
    request = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"Render rejected {component} deployment (HTTP {error.code})"
        ) from None
    except (OSError, ValueError):
        # URL-bearing exception messages and response bodies can contain credentials.
        raise SystemExit(
            f"Render request failed for {component}; inspect Render before retrying"
        ) from None
    if status not in {200, 202}:
        raise SystemExit(f"Unexpected Render response (HTTP {status})")
    deploy_id = None
    try:
        deploy_id = json.loads(body).get("deploy", {}).get("id")
    except (ValueError, AttributeError, TypeError):
        pass
    if isinstance(deploy_id, str) and re.fullmatch(r"dep-[a-z0-9]+", deploy_id):
        print(f"Render accepted {component} commit {sha}: {deploy_id}")
    else:
        print(f"Render accepted or queued {component} commit {sha} (HTTP {status})")
    print(
        "Acceptance is not proof of a live deployment; verify the Render deployment record."
    )


if __name__ == "__main__":
    sys.exit(main())
