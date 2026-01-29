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