# Substack Notes Scraper for AWS Lambda

This project contains a serverless scraper for Substack Notes. It runs as a containerized application on AWS Lambda, using Python and Playwright to automate data collection.

The scraper fetches notes based on configurable search jobs, normalizes the data, and sends the results to a webhook.

---

## Architecture Overview

- **Language**: Python 3
- **Automation**: Playwright with a headless Chromium browser.
- **Deployment**: AWS Lambda (via a Docker container image).
- **Container Registry**: Amazon Elastic Container Registry (ECR).

This architecture was chosen because it's the most reliable way to run Playwright on AWS, as the official Microsoft Playwright Docker image includes all necessary browser binaries and system dependencies, avoiding the `GLIBC` errors and complexity associated with Lambda Layers.

---

## Project Contents

- `main.py`: The core Python script containing the scraper logic and Lambda handler.
- `Dockerfile`: Instructions to build the Lambda-compatible container image.
- `requirements.txt`: A minimal list of Python package dependencies.
- `config.json`: Default search jobs for scheduled runs.
- `test-event.json`: A sample payload for on-demand testing in the Lambda console.
- `.gitignore`: Standard file to exclude unnecessary files from Git.
- `README.md`: This setup and deployment guide.

---

## Deployment Instructions

These steps will guide you through building the Docker image, pushing it to your private AWS registry, and deploying it as a Lambda function.

### Prerequisites

1.  **Docker Desktop**: Install from the [official Docker website](https://www.docker.com/products/docker-desktop/).
2.  **AWS Account**: An active AWS account with permissions to manage ECR and Lambda.
3.  **AWS CLI**: [Install and configure](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) the AWS Command Line Interface.

### Step 1: Clone the Repository

First, get the project files onto your local machine.

```sh
git clone <your-repo-url>
cd <repository-name>
```

### Step 2: Build the Docker Image

This command builds the container image from the `Dockerfile`. The `--platform linux/amd64` flag is crucial for ensuring the image is compatible with the AWS Lambda environment, especially when building on an Apple Silicon (M1/M2/M3) Mac.

```sh
docker build --platform linux/amd64 -t substack-scraper .
```

### Step 3: Create an ECR Repository

Your Docker image needs a home in AWS. Create a private ECR repository to store it. You only need to do this once.

1.  Navigate to the **ECR** service in the AWS Console.
2.  Click **Create repository**.
3.  Set the **Repository name** to `substack-scraper` and click **Create repository**.

### Step 4: Authenticate Docker with ECR

Next, get a temporary password from AWS and use it to log your local Docker client into your private ECR.

_In the AWS Console, navigate to your `substack-scraper` ECR repository and click the **"View push commands"** button in the top right. It will provide you with the exact commands for your account._

The command will look like this:

```sh
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.us-east-1.amazonaws.com
```

_You will need to replace the region and account ID with your own._

### Step 5: Tag and Push the Image to ECR

Now, tag your locally built image with the ECR repository URI and push it to AWS.

```sh
# Tag the image
docker tag substack-scraper:latest <your-aws-account-id>[.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest](https://.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest)

# Push the image
docker push <your-aws-account-id>[.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest](https://.dkr.ecr.us-east-1.amazonaws.com/substack-scraper:latest)
```

### Step 6: Create and Configure the Lambda Function

With your image in ECR, you can now create the Lambda function.

1.  Navigate to the **Lambda** service in the AWS Console.
2.  Click **Create function**.
3.  Select the **Container image** option.
4.  Under **Basic information**:
    - **Function name**: `substack-scraper`
    - **Container image URI**: Click **Browse images** and select the `substack-scraper:latest` image from your ECR repository.
5.  Click **Create function**.

### Step 7: Adjust Function Settings

After the function is created, you need to configure its resources and environment.

1.  Navigate to the function's page and click the **Configuration** tab.
2.  Go to **General configuration** -\> **Edit**.
    - **Memory**: Set to at least **1024 MB**. A good starting point is **1536 MB**.
    - **Timeout**: Set to **5 minutes** (`0 min 30 sec` is too short).
3.  Go to **Environment variables** -\> **Edit**.
    - Add a variable with the key `WEBHOOK_URL` and the value of your target webhook endpoint.

---

## Usage

You can run the scraper in two ways:

### 1\. On-Demand (Testing)

Use the **Test** tab in the Lambda console. Create a new test event using the contents of the `test-event.json` file from this repository. This allows you to run specific, one-off jobs.

### 2\. Scheduled (Production)

To run the scraper on a schedule (e.g., daily), create a trigger.

1.  In the Lambda function's page, click **Add trigger**.
2.  Select **EventBridge (CloudWatch Events)** as the source.
3.  Choose **Create a new rule**.
4.  Give the rule a name (e.g., `RunSubstackScraperDaily`).
5.  Select **Schedule expression** and enter a cron expression (e.g., `cron(0 12 * * ? *)` to run at 12:00 PM UTC every day).
6.  Click **Add**.

When triggered by a schedule, the scraper will use the jobs defined in the `config.json` file.
