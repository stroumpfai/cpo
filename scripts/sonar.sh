#!/usr/bin/env bash
# Run the SonarQube analysis for the CPO project.
# Usage:  bash scripts/sonar.sh
#
# Override any value with environment variables:
#   SONAR_HOST_URL  (default: http://localhost:9000)
#   SONAR_TOKEN     (default: token below)
#   SONAR_PROJECT   (default: cpo)

set -euo pipefail

SONAR_HOST_URL="${SONAR_HOST_URL:-http://localhost:9000}"
SONAR_TOKEN="${SONAR_TOKEN:-sqp_5bc8a7003ab72fa2b2eac57491b9837f6586a03e}"
SONAR_PROJECT="${SONAR_PROJECT:-cpo}"

pysonar \
  --sonar-host-url="$SONAR_HOST_URL" \
  --sonar-token="$SONAR_TOKEN" \
  --sonar-project-key="$SONAR_PROJECT"
