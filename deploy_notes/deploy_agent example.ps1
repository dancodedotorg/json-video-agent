# Set your Google Cloud Project ID
$env:GOOGLE_CLOUD_PROJECT = <cloud project name>

# Set your desired Google Cloud Location
$env:GOOGLE_CLOUD_LOCATION = "us-central1" # Probably this, but could be different

# Set the path to your agent code directory
$env:AGENT_PATH = "..\json_video_agent"

# Set a name for your Cloud Run service (optional)
$env:SERVICE_NAME = "json-video-service"

# Set an application name (optional)
$env:APP_NAME = "json_video_agent"

Write-Host "Environment variables set for this session."

adk deploy cloud_run `
--project=$env:GOOGLE_CLOUD_PROJECT `
--region=$env:GOOGLE_CLOUD_LOCATION `
--service_name=$env:SERVICE_NAME `
--app_name=$env:APP_NAME `
--with_ui `
$env:AGENT_PATH