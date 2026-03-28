# OSS Issue Watcher

Get email notifications when new beginner-friendly issues are opened on open source projects you want to contribute to.

## Currently Watching (50 repos)

| Category | Repo |
|----------|------|
| **Spring** | spring-projects/spring-boot · spring-projects/spring-kafka |
| **Kafka / Messaging** | kafbat/kafka-ui · tchiotludo/akhq · apache/dubbo |
| **Testing** | testcontainers/testcontainers-java |
| **Auth / Identity** | keycloak/keycloak · JanssenProject/jans |
| **CDC / Streaming** | debezium/debezium · seata/seata |
| **Cloud Native** | quarkusio/quarkus · kestra-io/kestra · line/armeria · camunda/camunda · alibaba/nacos · alibaba/Sentinel |
| **Search / Databases** | elastic/elasticsearch · opensearch-project/OpenSearch · questdb/questdb · dbeaver/dbeaver · apache/doris · apache/shardingsphere · crate/crate · hazelcast/hazelcast · vespa-engine/vespa · Graylog2/graylog2-server |
| **Observability** | apache/skywalking |
| **Static Analysis** | spotbugs/spotbugs · find-sec-bugs/find-sec-bugs · pmd/pmd · zaproxy/zaproxy |
| **Build / Dev Tools** | bazelbuild/bazel · GoogleContainerTools/jib · oracle/opengrok · typetools/checker-framework |
| **Libraries** | eclipse/eclipse-collections · graphhopper/graphhopper · allure-framework/allure2 |
| **JVM / Platform** | eclipse/openj9 · Sable/soot |
| **Data / Research** | google/data-transfer-project · OpenRefine/OpenRefine · JabRef/jabref |
| **Android / Mobile** | AntennaPod/AntennaPod · TeamNewPipe/NewPipe · facebook/fresco |
| **Other** | bisq-network/bisq · MovingBlocks/Terasology · UniversalMediaServer/UniversalMediaServer · crossoverJie/cim · SasanLabs/VulnerableApp |

## Setup (~10 minutes)

### 1. Create Your Repo

Fork or clone this project and push it to a **public** GitHub repo (public = unlimited free Actions minutes).

### 2. Gmail App Password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (requires 2FA enabled)
2. Create an app named `OSS Issue Watcher`
3. Copy the 16-character password

### 3. GitHub Personal Access Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → **Generate new token (classic)**
2. Name: `oss-issue-watcher`, scope: **`public_repo`** only
3. Copy the token

### 4. Add Secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `GH_TOKEN` | GitHub token from step 3 |
| `SMTP_USERNAME` | Your Gmail address |
| `SMTP_PASSWORD` | App password from step 2 |
| `NOTIFY_EMAIL` | Where to send notifications |

### 5. Test It

Go to **Actions → OSS Issue Watcher → Run workflow** and check your email after ~30 seconds.

## How It Works

- Runs every 4 hours via GitHub Actions
- Checks each repo for new issues with the configured labels
- Tracks seen issues so you only get notified once per issue
- Sends a formatted HTML email only when new issues are found

## Add More Repos

Edit `check_issues.py` and add to `WATCHED_REPOS`:

```python
{
    "owner": "apache",
    "repo": "kafka",
    "labels": ["good first issue"],
},
```

## FAQ

**Will I get spammed?**
No — you only get an email when new issues appear. Already-seen issues are tracked and skipped.

**Is this free?**
Yes. GitHub Actions is free for public repos. Gmail SMTP is free.

**The workflow stopped running?**
GitHub disables Actions after 60 days of no repo activity. Push a commit or trigger the workflow manually to re-enable.

**How do I change the frequency?**
Edit the cron in `.github/workflows/watch-issues.yml`. Examples:
- Every hour: `'0 * * * *'`
- Every 4 hours: `'0 */4 * * *'` (default)
- Every 6 hours: `'0 */6 * * *'`
