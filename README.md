# OSS Issue Watcher

Get **personalised email digests** of new open source issues — filtered by your difficulty range, tech areas, and capped at 5 issues — with a **Gemini AI score (1–10)** and plain-English summary of what needs to be done, attached as a CSV.

## How It Works

1. Runs every 4 hours via GitHub Actions (free, no server)
2. Checks 90+ repos for new issues across beginner → intermediate labels
3. Sends the top 50 newest to Gemini — scores each 1–10 and summarises the fix
4. For each configured user: filters by their difficulty range + tech areas, caps at `max_issues`, sends a personalised HTML email with CSV attached

---

## Difficulty Levels

Issues are tagged 1–10 based on the label used:

| Level | Labels | What it means |
| --- | --- | --- |
| 1 | `good first issue`, `first-timers-only` | Typos, tiny fixes — absolute beginners |
| 2 | `beginner`, `starter`, `low-hanging-fruit` | Simple but needs some code reading |
| 3 | `documentation`, `docs`, `readme` | Writing/improving docs |
| 4 | `help wanted`, `up-for-grabs`, `contributions welcome` | Well-scoped, maintainer wants help |
| 5 | `hacktoberfest` | October event — usually beginner-welcoming |
| 6 | `bug`, `enhancement`, `feature request` | Needs debugging or design sense |
| 7 | `refactoring`, `tech-debt`, `cleanup` | Needs solid codebase understanding |
| 8 | `needs-triage`, `needs-investigation` | Deep project context required |
| 9 | `performance`, `security`, `vulnerability` | Domain expertise required |
| 10 | `core`, `RFC`, `breaking-change` | Co-maintainer territory |

> Set `difficulty_min` and `difficulty_max` to the **same value** to get only that exact level.
> Set a range (e.g. `1–7`) to get everything up to that difficulty.

---

## Currently Watching (90+ repos)

| Category | Repos |
| --- | --- |
| **Spring** | spring-boot · spring-kafka · spring-framework |
| **Kafka / Messaging** | apache/kafka · kafka-ui · akhq · apache/dubbo · apache/pulsar |
| **Streaming / Pipelines** | apache/flink · apache/beam · debezium · seata |
| **Testing** | testcontainers-java · mockito · wiremock · junit5 · assertj · allure2 |
| **Auth / Identity** | keycloak · JanssenProject/jans |
| **Cloud Native / Microservices** | quarkus · micronaut-core · helidon · vert.x · netty · ktor · armeria · kestra · dropwizard · grpc-java |
| **API / Integration** | openapi-generator · mapstruct · OpenMetadata |
| **Databases** | elasticsearch · OpenSearch · questdb · dbeaver · apache/doris · shardingsphere · crate · hazelcast · vespa · lettuce · liquibase · flyway |
| **SRE / Observability** | grafana · loki · tempo · prometheus · alertmanager · jaeger · opentelemetry-collector · opentelemetry-java · skywalking · micrometer · thanos · VictoriaMetrics · graylog2-server |
| **Kubernetes / Infra** | kubernetes · ingress-nginx · cilium · cortex · argo-workflows · argo-cd · istio · helm · terraform |
| **Build / Dev Tools** | gradle · bazel · jib · opengrok · checker-framework · spotbugs · pmd |
| **Security** | zaproxy · find-sec-bugs · keycloak · VulnerableApp |
| **Frontend / Other** | react · next.js · nest · fastapi · flask · AntennaPod · NewPipe |

---

## Setup (~15 minutes)

### 1. Fork this repo

Keep it **public** — public repos get unlimited free Actions minutes.

---

### 2. Get a Gmail app password

You need this before you can add the `SMTP_PASSWORD` secret.

1. Sign in to [myaccount.google.com](https://myaccount.google.com) with the Gmail you want to **send from**
2. Go to **Security → 2-Step Verification** and make sure it is **ON** (app passwords won't appear otherwise)
3. Search **"App passwords"** in the search bar at the top
4. Click **App passwords** → type a name like `oss-issue-watcher` → click **Create**
5. Google shows a **16-character password** — copy it immediately, it's shown once only. Remove spaces when pasting.

---

### 3. Get a GitHub personal access token

Used to avoid GitHub API rate limits when fetching issues.

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → **Fine-grained tokens → Generate new token**
2. Name: `oss-issue-watcher`
3. Repository access: **Public repositories (read-only)**
4. Permissions: **Contents → Read-only**
5. Click **Generate token** and copy it

---

### 4. Get a Gemini API key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click **Create API key** → select any project (or create one)
3. Copy the key — free tier, no billing required

---

### 5. Add Secrets

Go to your fork: **Settings → Secrets and variables → Actions → Secrets tab → New repository secret**

Add each of these:

| Secret | Value |
| --- | --- |
| `SMTP_USERNAME` | The Gmail address you're sending from (e.g. `you@gmail.com`) |
| `SMTP_PASSWORD` | The 16-char app password from step 2 |
| `GEMINI_API_KEY` | The key from step 4 |
| `GEMINI_MODEL` | e.g. `gemini-2.5-flash` (optional, default: `gemini-2.0-flash`) |
| `GH_TOKEN` | The token from step 3 |
| `NOTIFY_EMAIL` | Your receiving email — only needed if you skip step 6 below |

---

### 6. Configure who gets what (Variables)

Go to your fork: **Settings → Secrets and variables → Actions → Variables tab → New repository variable**

#### Option A — Multi-user JSON (recommended)

Create one variable named `USER_CONFIGS` with a JSON array — one object per recipient:

```json
[
  {
    "email": "you@gmail.com",
    "name": "Your Name",
    "max_issues": 5,
    "difficulty_min": 1,
    "difficulty_max": 7,
    "areas": ["SRE", "Java", "Kubernetes", "Observability", "Testing"]
  }
]
```

Add more objects to the array for more recipients — each gets a filtered email based on their own prefs.

**All supported areas:**

| Area | What's covered |
| --- | --- |
| `Java` | Any Java repo (broadest filter — catches everything) |
| `Spring` | spring-boot, spring-framework, spring-kafka |
| `Backend` | quarkus, micronaut, helidon, vert.x, netty, armeria, dropwizard, grpc-java, resilience4j |
| `Kotlin` | ktor |
| `Messaging` | apache/kafka, kafka-ui, akhq, apache/pulsar, apache/dubbo |
| `Streaming` | apache/flink, apache/beam, debezium |
| `Testing` | testcontainers-java, mockito, wiremock, junit5, assertj, allure2 |
| `Security` | keycloak, jans, zaproxy, find-sec-bugs, VulnerableApp |
| `SRE` | grafana, loki, tempo, prometheus, alertmanager, jaeger, opentelemetry, thanos, VictoriaMetrics, kubernetes, cilium, argo-cd, argo-workflows, istio, helm, terraform, skywalking, micrometer, graylog2 |
| `Observability` | grafana, loki, tempo, prometheus, jaeger, opentelemetry, thanos, VictoriaMetrics, skywalking, micrometer, cortex, graylog2 |
| `Kubernetes` | kubernetes, ingress-nginx, cilium, argo-workflows, argo-cd, istio, helm, jib |
| `IaC` | terraform |
| `Databases` | elasticsearch, OpenSearch, questdb, dbeaver, doris, shardingsphere, crate, hazelcast, vespa, lettuce, liquibase, flyway, OpenMetadata |
| `Search` | elasticsearch, OpenSearch, vespa |
| `Workflow` | kestra, camunda |
| `Cloud Native` | nacos, Sentinel |
| `Distributed` | seata |
| `Build` | gradle, bazel, jib, spotbugs, pmd, checker-framework |
| `Tools` | dbeaver, opengrok |
| `API` | openapi-generator, mapstruct |
| `Data` | OpenRefine |
| `Frontend` | react, next.js |
| `JavaScript` | react, next.js, nest |
| `Python` | fastapi, flask |
| `Mobile` | AntennaPod, NewPipe |
| `Android` | AntennaPod, NewPipe |

> **Tip:** Set `difficulty_min` and `difficulty_max` to the same number for an exact level only (e.g. both `4` = only `help wanted` issues). Set a range like `1–7` to get everything up to that difficulty.

#### Option B — Single user (simpler, no JSON)

Skip `USER_CONFIGS` and set these individual variables instead:

| Variable | Example | What it does |
| --- | --- | --- |
| `NOTIFY_NAME` | `Naman` | Name in the email greeting |
| `MAX_ISSUES` | `5` | Max issues per email |
| `DIFFICULTY_MIN` | `1` | Minimum difficulty (1–10) |
| `DIFFICULTY_MAX` | `7` | Maximum difficulty (1–10) |
| `AREAS` | `SRE,Java,Kubernetes` | Comma-separated areas to watch |

The `NOTIFY_EMAIL` secret from step 5 is used as the recipient.

---

### 7. (Optional) Change the Gemini model

Add a **secret** `GEMINI_MODEL` = `gemini-2.5-flash` for better analysis quality.
Default is `gemini-2.0-flash`. Both are free tier — cron uses only 6 requests/day, well within limits.

---

### 8. Test it

Go to: **Actions → OSS Issue Watcher → Run workflow → Run workflow**

The Actions log prints every repo checked, issues found, Gemini result, and email delivery status. Check your inbox within ~60 seconds.

> **First run note:** `seen_issues.json` starts empty so you'll be notified of all currently open matching issues. After that, only new issues trigger emails.

---

## Testing Locally

```bash
export GH_TOKEN=your_token
export SMTP_USERNAME=you@gmail.com
export SMTP_PASSWORD=your_app_password
export GEMINI_API_KEY=your_gemini_key
export GEMINI_MODEL=gemini-2.5-flash
export USER_CONFIGS='[{"email":"you@gmail.com","name":"You","max_issues":5,"difficulty_min":1,"difficulty_max":7,"areas":["SRE","Java"]}]'

python check_issues.py
```

Force a fresh run (re-notify all current issues):

```bash
rm -f seen_issues.json && python check_issues.py
```

---

## Add / Remove Repos

Edit [`repos.json`](repos.json). Each entry:

```json
{ "owner": "apache", "repo": "kafka", "labels": ["good first issue", "help wanted"], "areas": ["Java", "Messaging"] }
```

The `areas` field controls which users receive issues from that repo (based on their `areas` preference).

---

## Claiming an Issue

See [`CLAIMING_ISSUES.md`](CLAIMING_ISSUES.md) — covers everything from reading the CSV to opening a draft PR.

---

## FAQ

**Will I get spammed?**
No. Each issue ID is stored in `seen_issues.json` — once notified, never again.

**What if Gemini fails?**
Email still sends using label-based difficulty scores. Gemini errors are logged in the Actions run.

**Same difficulty_min and difficulty_max?**
Valid — e.g. both `4` means only `help wanted` issues. Both `6` means only `bug`/`enhancement` issues.

**No issues matched my filters?**
The log will say "No matching issues — skipping email." Either widen your difficulty range, add more areas, or wait for the next cron tick.

**The workflow stopped running?**
GitHub disables scheduled Actions after 60 days of repo inactivity. Push any commit or trigger manually.

**How do I change the frequency?**
Edit `.github/workflows/watch-issues.yml`:

```yaml
- cron: '0 */4 * * *'   # every 4 hours (default)
- cron: '0 */6 * * *'   # every 6 hours
- cron: '0 8 * * *'     # once daily at 8am UTC
```

**Is this free?**
Yes. GitHub Actions is free for public repos. Gmail SMTP is free. Gemini free tier covers 500 req/day.
