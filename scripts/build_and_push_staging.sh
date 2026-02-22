#!/usr/bin/env bash

set -euo pipefail

: "${ACR_NAME:?ACR_NAME is required}"
: "${RG:?RG is required}"

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="vehr-api:${GIT_SHA}"

echo "Using resource group: ${RG}"
az acr show --name "${ACR_NAME}" --resource-group "${RG}" --output none

echo "Logging into ACR: ${ACR_NAME}"
az acr login --name "${ACR_NAME}"

echo "Building and pushing image tag: ${IMAGE_TAG}"
az acr build --registry "${ACR_NAME}" --image "${IMAGE_TAG}" .

echo "Done: ${ACR_NAME}.azurecr.io/${IMAGE_TAG}"
