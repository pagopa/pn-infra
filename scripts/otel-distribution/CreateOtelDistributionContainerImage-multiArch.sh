#! /bin/bash -e
# Script to create image repository and pull image for amazon/aws-otel-collector
# Run once in CI/CD profile

CICD_PROFILE=cicd
AWS_REGION=eu-central-1
TAG=v2.28.1
REPOSITORY=aws-otel-agent-injector ## ECR repository to host the container image - needs to be created before run this script
IMAGE=$REPOSITORY:$TAG
# Build a multi-arch image so the SAME tag works for both X86_64 (AMD) and ARM64 ECS tasks.
# IMPORTANT: do NOT rely on the build host architecture. Building on an Apple Silicon (arm64)
# machine without an explicit platform produces an arm64-only image; when the X86_64 ECS task
# pulls it the sidecar-injector container cannot start, the agent jar is never copied into
# /xray, and the microservice fails with:
#   "Error opening zip file or JAR manifest missing : /xray/aws-opentelemetry-agent.jar".
PLATFORMS=linux/amd64,linux/arm64

# Use docker if available, otherwise fall back to podman.
CONTAINER_TOOL=${CONTAINER_TOOL:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}
echo "Using container tool: ${CONTAINER_TOOL}"

CICD_ACCOUNT=$(aws sts get-caller-identity --profile $CICD_PROFILE --query 'Account' | jq -r .)

echo "Creating repo ${REPOSITORY} on account ${CICD_ACCOUNT}"

# Registry login
aws ecr get-login-password --region $AWS_REGION --profile $CICD_PROFILE | $CONTAINER_TOOL login --username AWS --password-stdin $CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Remote Repository
REMOTE_REPOSITORY=$CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$REPOSITORY:$TAG

# Cross-building arm64<->amd64 needs x86_64 emulation on Apple Silicon.
# Use Rosetta (already enabled on the `applehv` podman machine: `Rosetta: true`).
# Do NOT run `tonistiigi/binfmt --install` on Apple Silicon: it registers a qemu-x86_64
# binfmt handler that overrides Rosetta and segfaults on `apk`/`curl` during the amd64 build.
# If amd64 builds segfault, a leftover qemu-x86_64 handler is shadowing Rosetta; disable it:
#   podman machine ssh 'echo 0 | sudo tee /proc/sys/fs/binfmt_misc/qemu-x86_64'
# A clean `podman machine stop && podman machine start` also restores the Rosetta-only state.
# On a native amd64 CI/CD host no emulation is needed.
if [ "$CONTAINER_TOOL" = "docker" ]; then
  # docker buildx builds and pushes the multi-arch manifest in one step.
  docker buildx build \
    --platform "$PLATFORMS" \
    --build-arg version="$TAG" \
    -t "$REMOTE_REPOSITORY" \
    --push \
    .
else
  # podman builds a local manifest list, then pushes every architecture under the single tag.
  podman manifest rm "$IMAGE" 2>/dev/null || true
  podman build \
    --platform "$PLATFORMS" \
    --manifest "$IMAGE" \
    --build-arg version="$TAG" \
    .
  podman manifest push --all "$IMAGE" "docker://$REMOTE_REPOSITORY"
fi