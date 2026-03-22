#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${SPARK_VLLM_REPO_URL:-https://github.com/eugr/spark-vllm-docker.git}"
REPO_DIR="${SPARK_VLLM_REPO_DIR:-/tmp/spark-vllm-docker}"
REPO_REF="${SPARK_VLLM_REPO_REF:-2d749742e410a9467ca44cab354056e86015b6e8}"

if [ ! -d "${REPO_DIR}/.git" ]; then
  git clone "${REPO_URL}" "${REPO_DIR}"
fi

git -C "${REPO_DIR}" fetch --tags origin
git -C "${REPO_DIR}" checkout "${REPO_REF}"

"${REPO_DIR}/build-and-copy.sh"

docker image inspect vllm-node:latest >/dev/null
echo "Built vllm-node:latest from ${REPO_URL} @ ${REPO_REF}"
