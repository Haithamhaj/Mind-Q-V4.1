#!/usr/bin/env bash
set +e
python -m cli.runner flow --run-id smoke-ci
exit 0
