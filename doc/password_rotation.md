GitHub Actions secrets are the third place — after local .env and production env vars — where you had that password stored. Any time you rotate credentials, the mental checklist should be:

Local .env files (every clone you have)
Production deployment env vars
CI/CD secrets (GitHub Actions, CircleCI, whatever)
Any password managers, shared team vaults
Any documentation you've written


