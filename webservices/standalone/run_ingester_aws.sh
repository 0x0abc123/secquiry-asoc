#!/bin/bash
# usage:  run_ingester_aws.sh http://<collablio_host:port> <s3bucketname>
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR/..
python3 -m standalone.ingester_aws $1 $2