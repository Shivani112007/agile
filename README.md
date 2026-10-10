# SYNORA — Cloud-Based Student Skill Portfolio and Opportunity Matching System with CI/CD
Shivani R (24MIS0036) | Agile Development Process and DevOps Lab | Prof. Arunkumar A

## Run locally
    pip install -r requirements.txt
    python application.py          # http://localhost:5000
    python -m pytest -q            # tests
Register with `admin@portal.com` to get the admin role (override with ADMIN_EMAIL). Data is in-memory unless USE_DYNAMODB=1.

## Deploy on AWS
1. Run `bash create_tables.sh` (DynamoDB: students, opportunities, applications).
2. Push this repo to GitHub.
3. Elastic Beanstalk: create a Python app/environment. Env vars: USE_DYNAMODB=1, SECRET_KEY, AWS_REGION. Attach `iam-policy.json` to its instance role (IAM least privilege).
4. CodeBuild: new project, source = GitHub, uses `buildspec.yml`.
5. CodePipeline: Source (GitHub) -> Build (CodeBuild) -> Deploy (Elastic Beanstalk).
6. Monitoring: CloudWatch logs/alarms, `/health` endpoint, pipeline execution history.
Every `git push` now triggers build, test, and deployment automatically.


## UI / product
The application now uses the **SYNORA** product identity with the SkillSync positioning:
**Build your profile. Showcase your skills. Discover your opportunities.**

The existing Flask architecture is retained. The redesign is implemented in `application.py` with reusable template fragments/styles and remains compatible with the optional DynamoDB store. The UI includes:
- responsive landing page and product sections
- student dashboard with profile completion, skills and recommendations
- portfolio sections for skills, projects, certifications, achievements, interests and education
- searchable/filterable opportunities with transparent skill-match percentages
- application tracking and admin management dashboard
- validation, success/error feedback, confirmation prompts and useful empty states

The matching calculation remains intentionally simple: matched required skills / total required skills × 100.
