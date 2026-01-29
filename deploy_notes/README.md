# Notes on deploying to Google Cloud Run

[Based on these docs](https://google.github.io/adk-docs/deploy/cloud-run/)

## Preping environment and code

1) Setup your gcloud CLI so you are logged in and can see the project you want to deploy to
2) Update the example script file with the cloud project

## Fixing the CLI deploy bug

[This Git issue](https://github.com/google/adk-python/issues/209#issuecomment-3196978239) highlights a bug with google cloud deploy via CLI. The fix is to update a particular file in the venv you are running from. The correct version of this file is in this directory as `cli_deploy.py`.
- Go to the `\Lib\site-packages\google\adk\cli\` folder in your venv
- replace `cli_deploy.py` with the one from this directory

## Run the script


# REVISION!
This issue may be fixed, but now there may be a new one where you need to update the 2026 version of cli_deploy to get the xhtml2pdf to work. Here are notes from chatGPT:

The Fix
Search for the _DOCKERFILE_TEMPLATE string in your code (around line 65) and update it to include the apt-get commands. You must perform these steps as the root user (which is the default at the start of the Dockerfile) before the script switches to myuser.

Update the template to look like this:

```python
_DOCKERFILE_TEMPLATE: Final[str] = """
FROM python:3.11-slim
WORKDIR /app

# --- ADDED THIS SECTION ---
# Install system dependencies required for pycairo and other C-based extensions
USER root
RUN apt-get update && apt-get install -y \\
    gcc \\
    pkg-config \\
    libcairo2-dev \\
    && rm -rf /var/lib/apt/lists/*
# --------------------------

# Create a non-root user
RUN adduser --disabled-password --gecos "" myuser

# Switch to the non-root user
USER myuser

# Set up environment variables - Start
...
"""
```

**AND THEN STILL FIX THE VERTEXAI HARDCODED 1 AS WELL!**

Huh - also today I learned each agent file needs its own .env with vertexAI disabled