import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import logger

import json
import random
import sys
import re
import os
import time

import copy
import datetime
import uuid
import traceback

import base64
import io

######################################################
'''
Notes:
'''
######################################################

JSON_TMP_DIR = '/tmp/'    
NODE_INDEX = {'_':''}
UUIDS_USED = set()

def getNodeUUIDForUID(uid):
    global NODE_INDEX    
    nodeUUID = NODE_INDEX[uid] if uid in NODE_INDEX else None
    return nodeUUID

def storeNode(node):
    global NODE_INDEX
    global UUIDS_USED
    
    new_uuid = str(uuid.uuid4())
    while new_uuid in UUIDS_USED:
        new_uuid = str(uuid.uuid4())
    UUIDS_USED.add(new_uuid)
    NODE_INDEX[node[cnode.PROP_UID]] = new_uuid

def clearNodeIndex():
    global NODE_INDEX
    NODE_INDEX = {'_':''}
    
'''
public class QueryNodesPostData
{
    public List<string> uids {get; set;}
    public string field {get; set;}
    public string op {get; set;}
    public string val {get; set;}
    public int depth {get; set;}
    public string type {get; set;}
}
'''

def generateJsonForRootNode(rootNodeUID, client):
    try:
        jsonResponse =  client.fetchNodes(uid = rootNodeUID, body = True)
        nodesReturned = jsonResponse['nodes']
        for nodeResult in nodesReturned:
            storeNode(nodeResult)
            print(str(nodeResult))
            del nodeResult['dgraph.type']

        
        for nodeResult in nodesReturned:
            newUID = getNodeUUIDForUID(nodeResult[cnode.PROP_UID])
            nodeResult[cnode.PROP_UID] = newUID
            if cnode.PROP_PARENTLIST in nodeResult and nodeResult[cnode.PROP_PARENTLIST] is not None:
                for parent in nodeResult[cnode.PROP_PARENTLIST]:
                    newParentUID = getNodeUUIDForUID(parent[cnode.PROP_UID])
                    parent[cnode.PROP_UID] = newParentUID
            if cnode.PROP_CHILDLIST in nodeResult and nodeResult[cnode.PROP_CHILDLIST] is not None:
                for child in nodeResult[cnode.PROP_CHILDLIST]:
                    newChildUID = getNodeUUIDForUID(child[cnode.PROP_UID])
                    child[cnode.PROP_UID] = newChildUID
               
        jsonSaveFileName = JSON_TMP_DIR+'export-'+str(int(time.time()))+str(uuid.uuid4()).replace('-','')[:4]+'.json'
        with open(jsonSaveFileName,'w') as fw:
            json.dump(nodesReturned,fw)

        return jsonSaveFileName
            
    except Exception as e:
        logger.logEvent('an exception occurred while generating the report: '+str(e))
        logger.logEvent(traceback.format_exc())
        return ''


async def generate(metadata_dict):
    client = cclient.Client(metadata_dict['auth_token_hdr_val'])
    # fetch root node plus its children and serialise to json file
    jsonfile = generateJsonForRootNode(metadata_dict['under_uid'], client)
    # upload report as file attachment node

    logger.logEvent(f'jsonfile: {jsonfile}')


    params = { 'parentid': metadata_dict['under_uid'] }

    # Create the form with simple fields
    form = cclient.MultiPartForm()
    form.add_field('type', 'file_upload')
    form.add_field('_p', json.dumps(params))

    # Add the file
    form.add_file('filedata', jsonfile.split('/')[-1], fileHandle=open(jsonfile, "rb"))

    client.createFileNode(form)

    os.remove(jsonfile)

    return {"status":"OK","detail":"Generated Successfully"}

