# Substack Scraper on AWS Lambda

A serverless scraper for Substack Notes, designed to run as a containerized application on AWS Lambda. It uses Python and Playwright to fetch notes based on search jobs and sends the results to a webhook.

---

## Architecture

- **Language**: Python 3
- **Automation**: Playwright (Chromium)
- **Deployment**: AWS Lambda (Container Image)
- **Container Registry**: Amazon ECR

This project uses a container image based on Microsoft's official Playwright image. This is the most reliable method for running Playwright on Lambda, as it includes all necessary browser binaries and system dependencies, avoiding the `GLIBC` errors common with other approaches.

---

## Repository Contents

- `main.py`: The core Python script and Lambda handler.
- `Dockerfile`: Builds the Lambda-compatible container image.
- `requirements.txt`: Python package dependencies.
- `config.json`: Default search jobs for scheduled runs.
- `test-event.json`: A sample payload for on-demand Lambda testing.
- `.gitignore`: Standard git ignore file.
- `README.md`: This setup guide.

---

## Deployment Guide

### Prerequisites

- Docker Desktop
- An AWS Account
- [Configured AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

### 1. Build the Docker Image

Build the image using the `--platform` flag to ensure compatibility with the AWS Lambda environment.

```sh
docker build --platform linux/amd64 -t substack-scraper .
```

### 2\. Create ECR Repository & Get Push Commands

It's easiest to create the repository via the AWS website, as it provides the necessary login and push commands.

1.  In the AWS Console, navigate to the **ECR (Elastic Container Registry)** service.
2.  Click **Create repository**.
3.  Set the **Repository name** to `substack-scraper` and click **Create repository**.
4.  Once created, select the new repository and click the **View push commands** button in the top right.
5.  This modal contains the exact commands you need for the next two steps.

### 3\. Authenticate Docker with ECR

Copy the `aws ecr get-login-password...` command from the "View push commands" modal and run it in your terminal. It will authenticate your Docker client with your private AWS registry.

It will look like this:

```sh
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.us-east-1.amazonaws.com
```

### 4\. Tag and Push the Image

Copy the `docker tag` and `docker push` commands from the same modal. This will upload your locally built image to ECR.

```sh
# Tag the image
docker tag substack-scraper:latest <your-aws-account-id>[.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest](https://.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest)

# Push the image
docker push <your-aws-account-id>[.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest](https://.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest)
```

### 5\. Create the Lambda Function

1.  In the AWS Console, navigate to **Lambda** \> **Create function**.
2.  Select **Container image**.
3.  **Function name**: `substack-scraper`.
4.  **Container image URI**: Click **Browse images** and select the `substack-scraper:latest` image from your ECR repository.
5.  Click **Create function**.

### 6\. Configure Lambda Settings

After creation, adjust the function's configuration for performance and functionality.

1.  Navigate to **Configuration** \> **General configuration** \> **Edit**.
    - **Memory**: **1536 MB** (Recommended for Playwright)
    - **Timeout**: **5 minutes**
2.  Navigate to **Configuration** \> **Container image** \> **Edit**.
    - Under **Container image overrides**, verify the `Command` is set to `["main.lambda_handler"]`. This tells Lambda which function inside your Python script to run.
3.  Navigate to **Configuration** \> **Environment variables** \> **Edit**.
    - Click **Add environment variable**.
    - **Key**: `WEBHOOK_URL`
    - **Value**: `<your_webhook_endpoint>`

---

## Usage

### On-Demand Runs

Use the **Test** tab in the Lambda console. Create a new test event, paste the contents of `test-event.json`, and invoke the function to run specific, one-off jobs.

### Scheduled Runs

1.  In the function's main page, click **Add trigger**.
2.  Select **EventBridge (CloudWatch Events)**.
3.  Choose **Create a new rule**.
4.  Set the **Rule name** (e.g., `RunSubstackScraperDaily`).
5.  Select **Schedule expression** and provide a cron expression (e.g., `cron(0 12 * * ? *)` for a daily run at 12:00 PM UTC).
6.  Click **Add**.

Scheduled runs will use the jobs defined in the `config.json` file.

---

## Webhook Payload Structure

Your webhook endpoint will receive a `POST` request with a JSON body structured as follows. The top-level `results` key contains an array where each item corresponds to a job that was run.

```json
{
  "results": [
    {
      "job": {
        "keyword": "generative art",
        "author": null,
        "days_limit": 30
      },
      "notes": [
        {
          "id": 12345678,
          "type": "comment",
          "text": "This is the content of the Substack Note...",
          "author_handle": "authorhandle",
          "author_name": "Author Name",
          "created_at": "2025-08-21T14:30:00+00:00",
          "likes": 105,
          "comments_count": 12,
          "restacks": 25,
          "engagement": 142,
          "url": "[https://substack.com/note/12345678](https://substack.com/note/12345678)"
        }
      ]
    }
  ]
}
```

```

```
