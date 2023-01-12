'''
this script should run on an EC2 that was assigned the iam_for_ec2 role (defined in main.tf) upon launch
****???implement as a scheduled task in secquiry-asoc/webservices/taskhandlers
        may have to implement "system tasks" that are configured via config file instead of via secquiry task node
overview:
- connect to S3
- list objects in upload bucket
- iterate through objects
    - parse out the app_id
    - match the app_id to an app and tool scan folder in secquiry
        *assign a guid to baseline findings nodes, (or auto generate one?) -> possibly use the customdata field of the node
    - call invoke the /import endpoint on secquiry API (as a diffscan) and upload the scan file fetched from s3 bucket
    - delete or move the s3 object from the upload bucket
        https://stackoverflow.com/questions/30161700/move-files-between-two-aws-s3-buckets-using-boto3
'''
import sys
import os
import boto3
import re
import json
import collablio.node as cnode
import collablio.client as cclient
import secretstore
import logger

# assuming that aws creds are configured for the user|instance, run:
# usage:   python3 -m standalone.ingester_aws http://<collablio_host>:<port>  <s3_bucket_name>

if __name__ == '__main__':
    collablio_host_url = sys.argv[1] if len(sys.argv) > 1 else None
    s3_bucket_name = sys.argv[2] if len(sys.argv) > 2 else None
    sstore = secretstore.GetStore()
    #sstore.debug()
    client = cclient.Client(hostURL = collablio_host_url)
    client.setCreds(sstore.get('secquiry_user'),sstore.get('secquiry_pass'))

    logger.logEvent(f'ingester_aws running as {sstore.get("secquiry_user")} url: {collablio_host_url}, bucket: {s3_bucket_name}')

    findingsNodes = {}
    ignoreIDs = set()
    
    OBJKEY_PARTS_REGEX = '([a-f0-9-]+)-([0-9]{10})\.[a-zA-Z0-9_\-]'

    s3 = boto3.resource('s3')
    bucket = s3.Bucket(s3_bucket_name)
    object_summary_iterator = bucket.objects.all()
    for obj in object_summary_iterator:
        objkey = str(obj.key)
        logger.logEvent(f'ingester_aws processing {objkey}')
        app_id = None
        m = re.search(OBJKEY_PARTS_REGEX, objkey)
        if m is not None:
            app_id = m.group(1)
            timestamp = m.group(2)
            logger.logEvent(f'ingester_aws processing upload for {app_id}')
            # query collablio for task nodes
            if app_id not in ignoreIDs:
                if app_id not in findingsNodes:
                    jsonResponse = client.fetchNodes(field = cnode.PROP_CUSTOM, op = 'allofterms', val = app_id)
                    if 'nodes' in jsonResponse and len(jsonResponse['nodes']) > 0:
                        for nodeReturned in jsonResponse['nodes']:
                            findingsNodes[app_id] = nodeReturned[cnode.PROP_UID]
                    else:
                        ignoreIDs.add(app_id)
                        continue
                import_under_uid = findingsNodes[app_id]
                # s3.download_file('BUCKET_NAME', 'OBJECT_NAME', 'FILE_NAME')
                tmp_file_download_path = f'/tmp/{objkey}'
                s3client = boto3.client('s3')
                with open(tmp_file_download_path, 'wb') as tmpf:
                #with open(tmp_file_download_path, 'r+b') as tmpf:
                   s3client.download_fileobj(s3_bucket_name, objkey, tmpf)
                #   tmpf.seek(0)
                with open(tmp_file_download_path, 'rb') as tmpf:
                   form_data = cclient.MultiPartForm()
                   form_data.add_field('metadata',json.dumps({"diffscan":True,"under_uid":import_under_uid}))
                   form_data.add_file('file', objkey, tmpf)
                   importer_url = '/webservice/import/'
                   fileext = objkey.split('.')[-1]
                   if fileext == 'dsjson':
                     importer_url += 'dsjson'
                   else:
                     importer_url += 'sarif210'
                   client.createFileNode(form_data, importer_url)
                   s3client.delete_object(Bucket=s3_bucket_name, Key=objkey)
                os.remove(tmp_file_download_path)
            else:
                print(f'skip {app_id}')
                logger.logEvent(f'ingester_aws skip {app_id}')
