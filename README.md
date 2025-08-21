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

1.  **Docker Desktop**: Install from the [official Docker website](https://www.docker.com/products/docker-desktop/).
2.  **AWS CLI**:

    - [Install the AWS Command Line Interface](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html).
    - Configure the CLI by running `aws configure` and providing your **AWS Access Key ID**, **Secret Access Key**, and **Default region** (e.g., `us-east-1`).

      ```sh
      aws configure
      ```

### 1. Clone the Repository

Clone the project files to your local machine.

```sh
git clone https://github.com/roguetitan1703/substack-scraper-aws.git
cd substack-scraper-aws
```

### 2\. Build the Docker Image

Build the image using the `--platform` flag to ensure compatibility with the AWS Lambda environment.

```sh
docker build --platform linux/amd64 -t substack-scraper .
```

### 3\. Create ECR Repository & Get Push Commands

Create the repository using the AWS Management Console. The console provides a "View push commands" button which simplifies the next steps.

1.  In the AWS Console, navigate to the **ECR (Elastic Container Registry)** service.
2.  Click **Create repository**.
3.  Set the **Repository name** to `substack-scraper` and click **Create repository**.
4.  Once created, select the new repository and click the **View push commands** button in the top right. This modal contains the exact commands you need for the next two steps.

<img src="images/AWS%20ECR%20push%20commands%20window.png" alt="AWS ECR Push Commands" height="500">

### 4\. Authenticate Docker with ECR

Copy the `aws ecr get-login-password...` command (Step 1 in the modal) and run it in your terminal to authenticate your Docker client.

### 5\. Tag and Push the Image

Copy the `docker tag` and `docker push` commands (Steps 3 and 4 in the modal) to upload your locally built image to ECR.

### 6\. Create the Lambda Function

1.  In the AWS Console, navigate to **Lambda** \> **Create function**.

2.  Select the **Container image** option.

    <img src="images/Create%20Lambda%20function%20screen.png" alt="Create Lambda Function" height="600">

3.  Under **Basic information**, provide a **Function name** (`substack-scraper`).

4.  For the **Container image URI**, click **Browse images**. Select your `substack-scraper` repository and choose the image with the `latest` tag.

    <img src="images/Select%20container%20image%20modal.png" alt="Select Container Image Modal" height="400">

5.  Click **Create function**.

### 7\. Configure Lambda Settings

After creation, adjust the function's configuration.

1.  Navigate to **Configuration** \> **General configuration** \> **Edit**.

    - **Memory**: **1536 MB** (Recommended for Playwright)
    - **Timeout**: **5 minutes**

    <img src="images/Lambda%20general%20configuration.png" alt="Lambda General Configuration" height="200">

2.  Navigate to **Configuration** \> **Environment variables** \> **Edit**. Add the following:

    - **Required**:
      - `WEBHOOK_URL`: The endpoint where the scraper sends results.
    - **Optional**:
      - `DEBUG`: Set to `1` to enable verbose logging and include raw API data in the output.
      - `NOTE_SEARCH_MAX_PAGES`: A global override for the number of pages to scrape per job.

    <img src="images/Lambda%20environment%20variables.png" alt="Lambda Environment Variables" height="300">

3.  Navigate to **Configuration** \> **Container image** \> **Edit**.

    - Under **Container image overrides**, the `CMD` field can be left blank, as the `Dockerfile` already sets the correct default (`["main.lambda_handler"]`).

    <img src="images/Lambda%20CMD%20override%20setting.png" alt="Lambda CMD Override Setting" height="300">

---

## Usage

### On-Demand Runs

Use the **Test** tab in the Lambda console. Create a new test event, paste the contents of `test-event.json`, and invoke the function.

<img src="images/Lambda%20test%20event%20configuration.png" alt="Lambda Test Event Configuration" height="600">

A successful run will show a "succeeded" status and return the counts of notes found.

<img src="images/Successful%20Lambda%20execution%20log.jpg" alt="Successful Lambda Execution Log" height="600">

### Scheduled Runs

1.  In the function's main page, click **Add trigger**.
2.  Select **EventBridge (CloudWatch Events)**.
3.  Choose **Create a new rule**.
4.  Set the **Rule name** (e.g., `RunSubstackScraperDaily`).
5.  Select **Schedule expression** and provide a cron expression (e.g., `cron(0 12 * * ? *)` for a daily run at 12:00 PM UTC).
6.  Click **Add**.

Scheduled runs use the jobs defined in the `config.json` file.

---

## Webhook Payload Structure

Your webhook endpoint will receive a `POST` request with a JSON body structured as follows.

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
          "url": "https://substack.com/note/12345678"
        }
      ]
    }
  ]
}
```
