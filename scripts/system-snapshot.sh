#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' '--- docker ps ---'
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'

printf '\n%s\n' '--- docker stats ---'
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'

printf '\n%s\n' '--- nvidia-smi ---'
nvidia-smi --query-gpu=name,utilization.gpu,utilization.memory --format=csv,noheader,nounits || true

printf '\n%s\n' '--- gpu processes ---'
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader || true

printf '\n%s\n' '--- host memory ---'
free -h || true
