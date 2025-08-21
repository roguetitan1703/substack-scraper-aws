# Use the official Playwright Python image (has browsers + OS deps)
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

# metadata to keep builds reproducible
LABEL maintainer="you@example.com"
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install AWS Lambda Runtime Interface Client + Playwright Python package (pin)
# - awslambdaric makes the image Lambda-compatible
# - ensure the Python 'playwright' package is present (some Playwright images already include it; pin to required version)
RUN pip install --no-cache-dir awslambdaric playwright==1.46.0

# Copy your app deps and install them (other requirements)
COPY requirements.txt /var/task/requirements.txt
RUN if [ -s /var/task/requirements.txt ]; then pip install --no-cache-dir -r /var/task/requirements.txt; fi

# Add your function code
WORKDIR /var/task
COPY main.py config.json /var/task/

# Environment hardening/tweaks
ENV HOME=/tmp \
    PATH=/usr/local/bin:$PATH

# ENTRYPOINT: Awslambdaric acts as the Lambda Runtime Interface Client
ENTRYPOINT ["python", "-m", "awslambdaric"]
# CMD: the default handler module.function — adjust if your handler differs
CMD ["main.lambda_handler"]
