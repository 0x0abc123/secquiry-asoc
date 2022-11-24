import os
import re
import copy
import datetime
import sys
import uuid
import urllib.request
import urllib.parse
import json
import traceback
import collablio.node as cnode

# todo: load from config file
COLLABLIO_HOST = "http://127.0.0.1:5000"

class Client:

    def __init__(self, _auth_token_hdr_val):
        self.auth_token_hdr_val = _auth_token_hdr_val

    def executeHttpRequest(self, request):
        '''
        authreq = urllib.request.Request('http://127.0.0.1:5001/service/gettemptoken', data='null'.encode('utf8'), headers={'content-type': 'application/json'})
        response = urllib.request.urlopen(authreq)
        jsonResponse =  json.loads(response.read().decode('utf8'))
        if 'token' not in jsonResponse:
            #raise Exception()
            jsonResponse = {'token':''}
        '''
        request.headers['Authorization'] = self.auth_token_hdr_val   #jsonResponse['token']
        return urllib.request.urlopen(request)

    def fetchNodesRequest(self, querystring):
        req = urllib.request.Request(COLLABLIO_HOST+"/nodes"+querystring)
        response = self.executeHttpRequest(req)
        jsonResponse =  json.loads(response.read().decode('utf8'))
        if 'nodes' not in jsonResponse:
            #raise Exception()
            jsonResponse = {'nodes':[]}
        return jsonResponse

    def fetchNodes(self, uid = '', field = cnode.PROP_LABEL, op = 'eq', val = 'undefined', depth = 20, ntype = ''):
        querystring = f'?uid={uid}&field={field}&op={op}&val={val}&depth={depth}&type={ntype}'
        return self.fetchNodesRequest(querystring)

    # nodesToUpsert is a list of collablio.node.Node
    def upsertNodes(self, nodesToUpsert):
        apiNodesList = []
        for cNode in nodesToUpsert:
            cnode.recursiveConvertNodesToAPIFormat(cNode, apiNodesList)
        serialisedJson = json.dumps(apiNodesList).encode('utf8')
        req = urllib.request.Request(COLLABLIO_HOST+'/upsert', data=serialisedJson, headers={'content-type': 'application/json'})
        #response = urllib.request.urlopen(req)
        response = self.executeHttpRequest(req)
        # should return list of uids
        new_uids = json.loads(response.read().decode('utf8'))
        return new_uids