# Troubleshooting Guide

This document covers common errors and solutions for the Substack Scraper project, organized by the phase in which you might encounter them.

---

## 1. Docker Build Issues (On Your Local Machine)

### Error: Build fails with "file not found" for `main.py` or `config.json`

- **Symptom**: The build process stops with an error like `failed to compute cache key: "/config.json": not found`.
- **Cause**: The `docker build` command was run in a directory containing the `Dockerfile`, but the `config.json` file (or another file mentioned in a `COPY` instruction) is missing from that same directory.
- **Solution**: Ensure all required files (`main.py`, `config.json`, `requirements.txt`) are in the same folder as the `Dockerfile` before running the build command.

### Critical Issue: Build Succeeds, but Lambda Fails to Start

- **Symptom**: The `docker build` command completes without error, but when you invoke the Lambda function, it fails immediately. The CloudWatch logs show an error like `Runtime.InvalidEntrypoint` or `exec format error`, indicating an architecture mismatch.
- **Cause**: This is the most common issue for users on Apple Silicon (M1/M2/M3) Macs. Docker built an image for the `arm64` architecture by default, but AWS Lambda requires the `linux/amd64` architecture.
- **Solution**: You **must** rebuild the image using the `--platform` flag. This flag tells Docker to build an image that is compatible with Lambda's environment.
  ```sh
  # This is the correct command
  docker build --platform linux/amd64 -t substack-scraper .
  ```

---

## 2. AWS Deployment & Permission Issues

### Error: `docker push` fails with "denied: requested access to the resource is denied"

- **Symptom**: The push command fails with an access denied error.
- **Cause**: Your local Docker client is not authenticated with your AWS ECR account, or the authentication token has expired.
- **Solution**: Re-run the `aws ecr get-login-password...` command provided in the "View push commands" modal in the ECR console to get a new token.

### Error: Lambda fails with "Unable to retrieve ECR image" or Access Denied

- **Symptom**: The Lambda function fails on invocation, and CloudWatch logs indicate that the container image could not be pulled from ECR.
- **Cause**: The default IAM Execution Role created for a Lambda function does not have permission to access ECR.
- **Solution**: You need to attach the required policy to your function's execution role.
  1.  In the Lambda console, go to **Configuration** > **Permissions**.
  2.  Click on the **Role name** to open the IAM console.
  3.  Under **Permissions policies**, click **Add permissions** > **Attach policies**.
  4.  Search for and select the policy named **`AmazonEC2ContainerRegistryReadOnly`**.
  5.  Click **Add permissions**.

---

## 3. Lambda Runtime Errors (During Execution)

### Error: Function fails with "Process killed" or "Out of Memory"

- **Symptom**: The function stops abruptly. The CloudWatch log may end without a clear error or might include a message like `Runtime exited with error: signal: killed`.
- **Cause**: The 1536 MB of memory is insufficient for a particularly large or complex scraping job.
- **Solution**: Increase the function's memory.
  1.  Navigate to your Lambda function's **Configuration** > **General configuration** > **Edit**.
  2.  Increase the **Memory** to **2048 MB** or **3072 MB**. More memory also provides more vCPU power, which can help the job complete faster.

### Error: Function times out

- **Symptom**: The logs end with a "Task timed out" error message.
- **Cause**: The scraper is processing many pages, and the total execution time exceeded the configured Lambda timeout.
- **Solution**: Navigate to **Configuration** > **General configuration** > **Edit** and increase the **Timeout** to a higher value (e.g., 7 or 10 minutes).

### Error: Playwright "Browser not found" or "Page crashed"

- **Symptom**: The logs show a Python traceback from the Playwright library indicating the browser failed to launch or crashed.
- **Cause**: This is almost always a symptom of an incorrect Docker build (the architecture mismatch from step 1) or, less commonly, an out-of-memory issue.
- **Solution**:
  1.  First, confirm you built the image with `--platform linux/amd64`. This is the most likely cause. Rebuild and re-deploy if necessary.
  2.  If the build architecture is correct, increase the Lambda function's **Memory** as described above.

---

## 4. Webhook & Network Issues

### Problem: Webhook receives no data (but Lambda run "succeeded")

- **Symptom**: The Lambda function reports a successful run in the console, but the `notes` array in the webhook payload is empty.
- **Cause**: The search criteria (keyword, author, `days_limit`) were too narrow and genuinely returned no results from Substack.
- **Solution**:
  1.  **Broaden the Search**: Run a test with a wider `days_limit` or a more common keyword to confirm the scraper logic is working.
  2.  **Check CloudWatch Logs**: Go to the **Monitor** tab of your function and click **View CloudWatch logs**. Look for any warnings from the script, such as "API response was invalid".

### Advanced: Function in a VPC Cannot Reach Webhook

- **Symptom**: The scraper fails on any external network request, including calls to the Substack API or your webhook. The logs show connection timeout errors.
- **Cause**: This occurs if your Lambda function is placed within a VPC that does not have a route to the public internet. By default, functions are not in a VPC.
- **Solution**: This is an advanced configuration. The VPC must have a **NAT Gateway** and a route table that directs internet-bound traffic (`0.0.0.0/0`) to the NAT Gateway. Consult the [AWS documentation on Lambda networking](https://docs.aws.amazon.com/lambda/latest/dg/configuration-networking.html) for details.
