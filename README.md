# OSS Issue Watcher

Get email notifications when new contribution-ready issues open on open source projects you care about — with a **Gemini AI analysis** attached as a CSV scoring each issue 1–10 and summarising exactly what needs to be done.

## How It Works

- Runs every 4 hours via GitHub Actions (free, no server needed)
- Checks 90+ repos for new issues matching beginner-to-intermediate labels
- Tracks seen issues so you're never notified twice
- Sends a formatted HTML email only when new issues appear
- Calls **Gemini 2.5 Flash** to score each issue (1–10) and generate a plain-English summary of the fix — attached as a CSV

## Currently Watching (90+ repos)

| Category | Repos |
| --- | --- |
| **Spring** | spring-boot · spring-kafka · spring-framework |
| **Kafka / Messaging** | apache/kafka · kafka-ui · akhq · apache/dubbo · apache/pulsar |
| **Streaming / Pipelines** | apache/flink · apache/beam · debezium · seata |
| **Testing** | testcontainers-java · mockito · wiremock · junit5 · assertj |
| **Auth / Identity** | keycloak · JanssenProject/jans |
| **Cloud Native / Microservices** | quarkus · micronaut-core · helidon · vert.x · netty · ktor · armeria · kestra · dropwizard · grpc-java |
| **API / Integration** | openapi-generator · mapstruct · OpenMetadata |
| **Databases** | elasticsearch · OpenSearch · questdb · dbeaver · apache/doris · shardingsphere · crate · hazelcast · vespa · lettuce |
| **SRE / Observability** | grafana · loki · tempo · prometheus · alertmanager · jaeger · opentelemetry-collector · opentelemetry-java · skywalking · micrometer · thanos · VictoriaMetrics · graylog2-server |
| **Kubernetes / Infra** | kubernetes · ingress-nginx · cilium · cortex · argo-workflows · argo-cd · istio · helm · terraform |
| **Build / Dev Tools** | gradle · bazel · jib · opengrok · checker-framework · liquibase · flyway |
| **Static Analysis / Security** | spotbugs · find-sec-bugs · pmd · zaproxy · VulnerableApp |
| **Libraries / JVM** | eclipse-collections · graphhopper · resilience4j · allure2 · openj9 · soot · guava |
| **Data / Research** | data-transfer-project · OpenRefine · jabref |
| **Frontend / Other** | react · next.js · nest · fastapi · flask · AntennaPod · NewPipe |

## Labels Watched

Covers beginner to beginner-intermediate labels used across the ecosystem:

`good first issue` · `help wanted` · `up for grabs` · `up-for-grabs` · `starter task` · `please contribute` · `contributions welcome` · `status: ideal-for-contribution` · `type/good-first-issue` · and more

---

## Setup (~10 minutes)

### 1. Fork this repo

Fork to your GitHub account. Keep it **public** — public repos get unlimited free Actions minutes.

### 2. Add Secrets

Go to your fork → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value | Required? |
| --- | --- | --- |
| `SMTP_PASSWORD` | Gmail app password (see below) | **Yes** |
| `GEMINI_API_KEY` | From [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | **Yes** |
| `GH_TOKEN` | GitHub token with `public_repo` scope | Recommended |
| `SMTP_USERNAME` | Your sending Gmail address | Optional — default: `namanmahit@gmail.com` |
| `NOTIFY_EMAIL` | Recipient(s) — comma-separated for multiple | Optional — default: `namanworkie@gmail.com` |
| `GEMINI_MODEL` | e.g. `gemini-2.5-flash` | Optional — default: `gemini-2.0-flash` |

#### Getting your Gmail app password

1. Sign in to [myaccount.google.com](https://myaccount.google.com)
2. **Security → 2-Step Verification** — must be ON
3. Search **"App passwords"** at the top → create one named `oss-issue-watcher`
4. Copy the 16-char password (shown once) — paste as `SMTP_PASSWORD`, no spaces

#### Getting a GitHub token

[github.com/settings/tokens](https://github.com/settings/tokens) → Fine-grained token → `contents: read` scope only

#### Getting a Gemini API key

[aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Create API key → free tier, no billing needed

**Recommended model:** `gemini-2.5-flash` — best reasoning quality on free tier (500 req/day; cron uses 6/day)

### 3. Test it

Go to **Actions → OSS Issue Watcher → Run workflow** → click **Run workflow**.

Check the Actions log — it prints every repo checked, every new issue found, and whether the Gemini call and email succeeded. Check your inbox within ~60 seconds.

> **First run tip:** `seen_issues.json` starts empty, so the first run will notify you of all currently open matching issues. This is expected. After that, only new issues trigger emails.

---

## Testing Locally

```bash
# Set env vars
export GH_TOKEN=your_token
export SMTP_USERNAME=namanmahit@gmail.com
export SMTP_PASSWORD=your_app_password
export NOTIFY_EMAIL=namanworkie@gmail.com
export GEMINI_API_KEY=your_gemini_key
export GEMINI_MODEL=gemini-2.5-flash

# Run
python check_issues.py
```

To force a fresh run (re-notify all current issues):

```bash
rm -f seen_issues.json && python check_issues.py
```

---

## Add / Remove Repos

Edit [`repos.json`](repos.json). Each entry is:

```json
{ "owner": "apache", "repo": "kafka", "labels": ["good first issue", "help wanted"] }
```

Multiple labels = multiple API calls per repo, each deduped before emailing.

---

## Claiming an Issue

See [`CLAIMING_ISSUES.md`](CLAIMING_ISSUES.md) for the full workflow — from reading the Gemini CSV to opening a draft PR.

---

## FAQ

**Will I get spammed?**
No. Each issue ID is stored in `seen_issues.json` — once notified, never again.

**What if Gemini fails?**
The email still sends without the CSV attachment. Gemini errors are logged in the Actions run.

**Can I send to multiple people?**
Yes — set `NOTIFY_EMAIL` to `email1@gmail.com,email2@gmail.com`.

**The workflow stopped running?**
GitHub disables scheduled Actions after 60 days of repo inactivity. Push any commit or trigger manually to re-enable.

**How do I change the frequency?**
Edit `.github/workflows/watch-issues.yml`:

```yaml
- cron: '0 */4 * * *'   # every 4 hours (default)
- cron: '0 */6 * * *'   # every 6 hours
- cron: '0 8 * * *'     # once daily at 8am UTC
```

**Is this free?**
Yes. GitHub Actions is free for public repos. Gmail SMTP is free. Gemini free tier covers 500 req/day.
