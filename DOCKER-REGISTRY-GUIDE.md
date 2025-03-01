# Docker Registry Guide for PiBoat Server

This guide explains how to work with Docker images for the PiBoat Server project using GitHub Container Registry.

## Understanding Docker and Git

Docker images are large binary files that shouldn't be stored directly in Git repositories. Instead:

1. We store Dockerfiles and docker-compose.yml in our Git repository
2. We use GitHub Container Registry (GHCR) to store the built Docker images
3. GitHub Actions automatically builds and pushes images when code is updated

## Using Pre-built Images

The docker-compose.yml file is configured to use pre-built images from GitHub Container Registry:

```yaml
services:
  relay-server:
    image: ghcr.io/${GITHUB_REPOSITORY}/relay-server:latest
    # ... configuration ...
    
  web-client:
    image: ghcr.io/${GITHUB_REPOSITORY}/web-client:latest
    # ... configuration ...
```

To use these images:

1. Make sure you're logged in to GitHub Container Registry:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

2. Run with docker-compose:
   ```bash
   docker-compose up
   ```

## Building Images Locally

To build images locally:

1. Uncomment the build sections in docker-compose.yml:
   ```yaml
   services:
     relay-server:
       # image: ghcr.io/${GITHUB_REPOSITORY}/relay-server:latest
       build:
         context: .
         dockerfile: server.Dockerfile
       # ... rest of config ...
   ```

2. Run with docker-compose:
   ```bash
   docker-compose up --build
   ```

## Pushing Images Manually

If you need to push images manually:

1. Build the images:
   ```bash
   docker build -t ghcr.io/USERNAME/piboat-server/relay-server:latest -f server.Dockerfile .
   docker build -t ghcr.io/USERNAME/piboat-server/web-client:latest -f web-client.Dockerfile .
   ```

2. Login to GitHub Container Registry:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

3. Push the images:
   ```bash
   docker push ghcr.io/USERNAME/piboat-server/relay-server:latest
   docker push ghcr.io/USERNAME/piboat-server/web-client:latest
   ```

## GitHub Actions Automation

This repository includes a GitHub Actions workflow that automatically:
1. Builds Docker images for both the relay-server and web-client
2. Pushes those images to GitHub Container Registry
3. Tags the images with the git commit SHA and branch/tag names

The workflow runs whenever:
- You push to the main branch
- You create a pull request to the main branch
- You manually trigger the workflow

## Making Your Images Public

By default, packages on GitHub Container Registry are private to your account/organization. To make them public:

1. Go to your GitHub repository
2. Click on the "Packages" tab
3. Click on the package you want to make public
4. Click on "Package settings"
5. Under "Danger Zone", select "Change visibility" and set to "Public"

## Secrets Required

For GitHub Actions to work properly, no additional secrets are required as it uses the built-in `GITHUB_TOKEN`.

For local development, you may want to create a Personal Access Token with appropriate permissions. 