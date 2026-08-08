GPT Ingest - cleaned repository

This repository contains the cleaned `gpt_ingest` tooling extracted from a larger workspace.

Files included:
- `gpt_ingest.sh` - main ingestion script
- `audit_tool/gpt_ingest_detect.py` - helper detection script

Credential & secrets guidance:
- Do NOT store personal access tokens (PATs) or other secrets in the repository.
- Use GitHub Secrets, environment variables, or a secrets manager for CI and runtime.
- Prefer fine-grained tokens, deploy keys, or GitHub Apps with least privilege.

To initialize locally and push to GitHub:

```bash
git init
git add .
git commit -m "Initial import of gpt_ingest tooling"
# create a new repo on GitHub, then:
# git remote add origin git@github.com:yourorg/gpt_ingest.git
# git branch -M main
# git push -u origin main
```
# gptingest
