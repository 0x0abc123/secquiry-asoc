#!/bin/bash
# usage:  run_ingester_aws.sh http://<collablio_host:port> <s3bucketname>
cd ..
python3 -m standalone.ingester_aws $1 $2