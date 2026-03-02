# Deploy merch7am API to AWS

Two options: **App Runner** (simplest) or **ECS Fargate** (industry standard).

---

## Prerequisites

- [AWS account](https://aws.amazon.com)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured (`aws configure`)
- [Docker](https://docs.docker.com/get-docker/) installed
- Backend code in a **GitHub** repo (for App Runner) or push to ECR (for ECS)

---

## Option 1: AWS App Runner (simplest)

App Runner deploys from GitHub and auto-scales. Good for getting started.

### Steps

1. **Push your backend to GitHub** (e.g. `your-org/merch-ai` or a separate `merch7am-api` repo)

2. **Create App Runner service**
   - AWS Console → App Runner → Create service
   - Source: **GitHub** → connect repo → select branch
   - Build: **Docker** → Dockerfile path: `backend/Dockerfile` (or `Dockerfile` if backend is repo root)
   - Deploy trigger: **Automatic** (deploys on push)

3. **Configure**
   - CPU: 1 vCPU, Memory: 2 GB
   - Port: **3001**
   - Add environment variables (see below)

4. **Get URL** – App Runner gives you `https://xxx.us-east-1.awsapprunner.com`

5. **Update theme** – Set chat widget and estimate API URL to your App Runner URL

### Environment variables (App Runner)

In App Runner → Configuration → Environment variables, add:

| Variable | Value |
|----------|-------|
| `OPENAI_API_KEY` | your key |
| `CORS_ORIGIN` | `https://merch7am.com,https://www.merch7am.com` |
| `RESEND_API_KEY` | (optional) |
| `ADMIN_EMAIL` | your email |
| `SHOPIFY_STORE_DOMAIN` | merch7am.myshopify.com |
| `SHOPIFY_STOREFRONT_TOKEN` | (optional, for chat) |

---

## Option 2: ECS Fargate (industry standard)

Uses Docker + ECR + ECS. More control, common in job requirements.

### 1. Build and push image to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name merch7am-api

# Get your AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push
cd backend
docker build -t merch7am-api .
docker tag merch7am-api:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/merch7am-api:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/merch7am-api:latest
```

### 2. Create ECS cluster and task

**Via Console:**
- ECS → Create cluster (e.g. `merch7am-cluster`)
- Task Definitions → Create (Fargate)
  - Image: `{account}.dkr.ecr.{region}.amazonaws.com/merch7am-api:latest`
  - Port: 3001
  - Environment variables: add all from `.env.example`
  - CPU: 0.25 vCPU, Memory: 0.5 GB (or 0.5 / 1 GB for production)

- Create Service
  - Launch type: Fargate
  - Load balancer: Application Load Balancer (ALB)
  - Target group: port 3001
  - Health check: `/api/health`

**Via AWS CLI / Terraform:** See [ECS docs](https://docs.aws.amazon.com/ecs/latest/developerguide/getting-started-fargate.html).

### 3. Expose via ALB

- ALB listener: HTTPS (443) → target group (port 3001)
- Optional: add custom domain (e.g. `api.merch7am.com`) with Route 53 + ACM certificate

---

## Local Docker test

Before deploying, test locally:

```bash
cd backend
docker build -t merch7am-api .
docker run -p 3001:3001 --env-file .env merch7am-api
```

Then open http://localhost:3001/api/health

---

## Notes

- **Estimate storage:** `data/estimates/` is ephemeral in containers. For persistence, add [EFS](https://docs.aws.amazon.com/efs/) (ECS) or switch to S3.
- **CORS:** Set `CORS_ORIGIN` to your production domain(s).
- **Secrets:** Use [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/) for sensitive env vars in production.
