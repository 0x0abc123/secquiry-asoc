'''
this script is run by ../scripts/setup.sh
'''
import json
import collablio.node as cnode
import collablio.client as cclient
import appconfig
import getpass
import authhelpers

# assuming that aws creds are configured for the user|instance, run:
# usage:   python3 -m standalone.ingester_aws http://<collablio_host>:<port>  <s3_bucket_name>
ADMIN_ACCOUNT_NAME = 'secquiryadmin'

if __name__ == '__main__':
    collablio_host_url = appconfig.getValue('collablio_url')
    while True:
        print(f'This will create the {ADMIN_ACCOUNT_NAME} account or reset its password')
        pass1 = getpass.getpass('Enter password: ')
        pass2 = getpass.getpass('Confirm password: ')
        if pass1 == pass2:
            break
        else:
            print('[!] Passwords did not match')

    client = cclient.client
    passwdhash = authhelpers.hash_password(pass2)
    cdata = json.dumps({authhelpers.PASSWD_FIELD:passwdhash, authhelpers.SSO_FIELD:False})

    jsonResponse = client.fetchNodes(field = cnode.PROP_LABEL, op = 'eq', val = ADMIN_ACCOUNT_NAME, ntype = cnode.TYPE_USER)
    if 'nodes' in jsonResponse and len(jsonResponse['nodes']) > 0:
        nodeReturned = jsonResponse['nodes'][0]
        nodeReturned[cnode.PROP_CUSTOM] = cdata
        nodesToUpsert = [nodeReturned]
        client.upsertNodes(nodesToUpsert, convertToAPIFormat=False)
    else:
        newusernode = cnode.Node(cnode.TYPE_USER)
        newusernode.Label = ADMIN_ACCOUNT_NAME
        newusernode.CustomData = cdata
        nodesToUpsert = [newusernode]
        client.upsertNodes(nodesToUpsert)
