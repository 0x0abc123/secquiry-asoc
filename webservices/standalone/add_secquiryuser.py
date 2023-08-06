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

if __name__ == '__main__':
    collablio_host_url = appconfig.getValue('collablio_url')
    
    is_admin = False
    is_sso = False
    pass2 = None

    print(f'This will create a user account or reset its password')
    
    username = input("Enter username: ")

    while True:
        admin = input("Is Admin? (y/n): ")
        if admin.lower() == "y":
            is_admin = True
        elif admin.lower() == "n":
            is_admin = False
        else:
            continue
        break

    while True:
        sso = input("Single Sign On user? (y/n): ")
        if sso.lower() == "y":
            is_sso = True
        elif sso.lower() == "n":
            is_sso = False
        else:
            continue
        break

    if not is_sso:
        while True:
            pass1 = getpass.getpass('Enter password: ')
            pass2 = getpass.getpass('Confirm password: ')
            if pass1 == pass2:
                break
            else:
                print('[!] Passwords did not match')
        

    client = cclient.client
    passwdhash = authhelpers.hash_password(pass2)
    cdata = json.dumps({authhelpers.PASSWD_FIELD:passwdhash, authhelpers.SSO_FIELD:is_sso, authhelpers.ADMIN_FIELD:is_admin})

    jsonResponse = client.fetchNodes(field = cnode.PROP_LABEL, op = 'eq', val = username, ntype = cnode.TYPE_USER)
    if 'nodes' in jsonResponse and len(jsonResponse['nodes']) > 0:
        nodeReturned = jsonResponse['nodes'][0]
        nodeReturned[cnode.PROP_CUSTOM] = cdata
        nodesToUpsert = [nodeReturned]
        client.upsertNodes(nodesToUpsert, convertToAPIFormat=False)
    else:
        newusernode = cnode.Node(cnode.TYPE_USER)
        newusernode.Label = username
        newusernode.CustomData = cdata
        nodesToUpsert = [newusernode]
        client.upsertNodes(nodesToUpsert)


