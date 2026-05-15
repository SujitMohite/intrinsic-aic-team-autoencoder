# Upload — Push to ECR & Register Submission

Source: [`docs/submission.md`](../../docs/submission.md). Credentials come from the **onboarding email** to the team leader.

## Prereqs

- AWS CLI installed.
- Credentials from onboarding email (Access Key ID, Secret, ECR repo URI for our team).
- Local `team-autoencoder:v1` image built and verified ([`00_packaging.md`](./00_packaging.md)).

## Step 1 — Configure AWS profile

```bash
aws configure --profile team_autoencoder
# Access Key ID: <from email>
# Secret Access Key: <from email>
# Default region name: us-east-1
# Default output format: json
```

```bash
export AWS_PROFILE=team_autoencoder
```

## Step 2 — Authenticate Docker against ECR

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
      973918476471.dkr.ecr.us-east-1.amazonaws.com
```

The login token expires after **12 hours**. If pushes fail with `no basic auth credentials`, re-run this step.

## Step 3 — Tag the image

```bash
docker tag team-autoencoder:v1 \
  973918476471.dkr.ecr.us-east-1.amazonaws.com/aic-team/team_autoencoder:v1
```

> **ECR tags are immutable.** Once `v1` exists in our repo, `v1` cannot be overwritten. Use `:v2`, `:v3`, or a commit SHA for subsequent submissions. Pushes with an existing tag fail silently.

Suggested tag convention: `<yyyymmdd>-<git-sha-short>-<note>` e.g. `20260514-abc1234-ae-v1`.

## Step 4 — Push

```bash
docker push 973918476471.dkr.ecr.us-east-1.amazonaws.com/aic-team/team_autoencoder:v1
```

Confirm the layers all push successfully. A push that ends in `Pushed` for each layer + a final digest is healthy.

## Step 5 — Register the submission in the portal

> Just pushing does **not** trigger evaluation. We have to point the portal at the image.

1. Copy the full URI: `973918476471.dkr.ecr.us-east-1.amazonaws.com/aic-team/team_autoencoder:v1`.
2. Sign in to the submission portal (credentials from onboarding email).
3. Open **AI for Industry Challenge** → **Submit**.
4. Select phase **Qualification**.
5. Paste the URI in the **OCI Image** field.
6. Click **Submit**.

## Step 6 — Watch the evaluation

| Status | Meaning |
| --- | --- |
| **Submitted** | Portal accepted the URI. |
| **Queued** | Waiting for an eval node. |
| **Running** | Container pulled, simulation running. |
| **Finished** | Done — scoring on the leaderboard. |
| **Failed** | Crashed (Python import error, etc.) or timed out. |

Queued → Finished typically takes **5–15 min**. Don't resubmit while Queued / Running.

## Daily quota

**1 submission per day.** Spend it deliberately. Failures count.

## When push fails

| Error | Fix |
| --- | --- |
| `no basic auth credentials` | ECR login expired — redo Step 2 |
| `denied: requested access to the resource is denied` | Wrong AWS profile / typo in URI / wrong team |
| `tag already exists` | ECR is immutable — bump tag |
| `network error` | Retry; if persistent, check `aws sts get-caller-identity` |

## When eval fails on the portal

See [`../03_policy/04_pitfalls.md`](../03_policy/04_pitfalls.md). The usual suspects:
- Heavy imports → discovery timeout.
- Wall-clock `time.sleep()`.
- Missing checkpoint (forgotten `COPY` in Dockerfile).
- Hard-coded `nic_card_0` etc.

If the portal shows **Failed** with empty logs, the heavy-imports path is the first hypothesis.

## What we do NOT do

- We do not run `aws ecr put-image` manually or any raw API call. `docker push` is the only supported path.
- We do not push without `:tag`. ECR rejects untagged manifests in our setup.
- We do not embed AWS credentials inside the image (`docker history` would expose them).
