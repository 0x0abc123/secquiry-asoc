#!/usr/bin/python3
import xml.etree.ElementTree as ETree
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

C_USAGE = '''Usage: {0} <project-label> <amass-output-file>
        import Amass raw console output file
'''

PROP_UID = "uid"
PROP_TYPE = "ty"
PROP_LABEL = "l"
PROP_DETAIL = "d"
PROP_TEXTDATA = "x"
PROP_CUSTOM = "c"
PROP_TIME = "t"
PROP_LASTMOD = "m"
PROP_BINARYDATA = "b"
PROP_EDITING = "e"
PROP_PARENTLIST = "in"
PROP_CHILDLIST = "out"
PROP_RELATIONS = "lnk"

TYPE_CLIENT = "Client"
TYPE_PROJECT = "Project"
TYPE_FOLDER = "Folder"
TYPE_HOST = "Host"
TYPE_PORT = "Port"
TYPE_TEXT = "Text"
TYPE_IMAGE = "Image"
TYPE_FILE = "File"
TYPE_NOTE = "Note"
TYPE_TABLE = "Table"
TYPE_ANNOTATION = "Annotation"
TYPE_TAG = "Tag"
TYPE_REPORT = "Report"
TYPE_SECTION = "Section"

def parseArgs():
    try:
        data = {}
        num_args = len(sys.argv)
        data['projectname'] = sys.argv[1]
        data['filename'] = sys.argv[2]

        if not data['projectname']:
            raise Exception()

        '''
        if not data['filename'].split('.')[-1].lower() in ['xml']:
            print("XML file required, got {}".format(data['filename']))
            raise Exception()
        '''
        return data
    except:
        print(C_USAGE.format(sys.argv[0]))
        exit(0)


#del foo.bar
class Node:
    
    def __init__(self, _type):
        self.Type = _type
        self.Children = []
        self.Parents = []
        self.UID = ''
        self.Label = ''
        self.Detail = ''
        self.CustomData = ''
        self.TextData = ''
        
    def convert(self):
        apiFormatNode = {}
        apiFormatNode[PROP_UID] = self.UID
        apiFormatNode[PROP_TYPE] = self.Type
        apiFormatNode[PROP_LABEL] = self.Label
        apiFormatNode[PROP_DETAIL] = self.Detail
        apiFormatNode[PROP_TEXTDATA] = self.TextData
        #only need to specify the parent UID for the host nodes if they don't have a UID (i.e. a new insert)
        apiFormatNode[PROP_PARENTLIST] = [{PROP_UID : self.Parents[0]}] if (len(self.Parents) > 0) else []
        apiFormatNode[PROP_CHILDLIST] = [{PROP_UID : child.UID} for child in self.Children]
        return apiFormatNode
        
#instead of NodeWithChildren classes, use a dict with an array of children:
# [{'host':hostNode, 'ports':[portNodes]},...]
# [{'port':portNode, 'textitems':[textNodes]},...]



argdata = parseArgs()

#etree = ETree.parse(argdata['filename'])

G_IPs = {}
G_ASNs = ''

# Run Amass
info_regex = '^[a-zA-Z0-9\._-]+ [a-z0-9\.,:]+$'
lineiterator = None
with open(argdata['filename'], 'r') as fB:
    lineiterator = fB.readlines()
    fB.close()
found_hosts = False
for line in lineiterator:
    print(line)
    l = line.strip()
    m = re.search(info_regex, l)
    if m:
        found_hosts = True
        tokens = l.split(' ')
        if len(tokens) > 1:
            ips = tokens[1].split(',')
            for i in ips:
                hostname = tokens[0].lower()
                try:
                    hostIPhns = G_IPs[i][C_DB_HNs]
                    hostIPhns.add(hostname)
                except:
                    tmpset = set()
                    tmpset.add(hostname)
                    G_IPs[i] = tmpset
    elif found_hosts and l.startswith('OWASP Amass v'):
        for remaining_line in lineiterator:
            G_ASNs += remaining_line + "\n"


allHosts = []

ASNsNode = Node(TYPE_TEXT)

for host in G_IPs:

    hostNode = Node(TYPE_HOST)
    hostNode.Label = host
    allHosts.append(hostNode)
    
    for hostname in G_IPs[host]:
        annotationNode = Node(TYPE_ANNOTATION)
        hostNode.Children.append(annotationNode)
        annotationNode.Label = '[name] '+hostname.lower()

    for c in hostNode.Children:
        c.Detail = '{} (amass {})'.format(hostNode.Label, argdata['projectname'])
        

ASNsNode.TextData = G_ASNs
ASNsNode.Label = "Amass ASN info"
ASNsNode.Detail = argdata['projectname']

def executeHttpRequest(request):
    authreq = urllib.request.Request('http://127.0.0.1:5001/service/gettemptoken', data='null'.encode('utf8'), headers={'content-type': 'application/json'})
    response = urllib.request.urlopen(authreq)
    jsonResponse =  json.loads(response.read().decode('utf8'))
    if 'token' not in jsonResponse:
        #raise Exception()
        jsonResponse = {'token':''}
    
    request.headers['Authorization'] = 'Bearer '+jsonResponse['token']
    return urllib.request.urlopen(request)

def fetchNodes(query):
    req = urllib.request.Request("http://127.0.0.1:5000/nodes"+query)
    response = executeHttpRequest(req)
    #response = urllib.request.urlopen("http://127.0.0.1:5000/nodes"+query)
    jsonResponse =  json.loads(response.read().decode('utf8'))
    if 'nodes' not in jsonResponse:
        #raise Exception()
        jsonResponse = {'nodes':[]}
    return jsonResponse


def recursiveConvertNodesToAPIFormat(node, listToAddTheNodeTo):
    listToAddTheNodeTo.append(node.convert())
    for child in node.Children:
        recursiveConvertNodesToAPIFormat(child, listToAddTheNodeTo)
        
#QueryNodesGet(string uid = null, string field=null, string op=null, string val=null, int depth = 0, string type = null)
                
#query to find projectname data['projectname']
querystring = '?uid=&field={}&op={}&val={}&depth={}&type={}'.format(\
    PROP_LABEL,\
    'eq',\
    urllib.parse.quote(argdata['projectname']),\
    20,\
    TYPE_PROJECT)
print("http://127.0.0.1:5000/nodes"+querystring)

try:
    jsonResponse =  fetchNodes(querystring)
    projectUID = ''
    for nodeResult in jsonResponse['nodes']:
        if nodeResult[PROP_LABEL] == argdata['projectname']:
            projectUID = nodeResult[PROP_UID]
            break
    print('located project '+projectUID)

    #query recursively to find existing hosts under projectname
    querystring = '?uid={}&field={}&op={}&val={}&depth={}&type={}'.format(\
        projectUID,\
        PROP_LASTMOD,\
        'gt',\
        0,\
        20,\
        TYPE_HOST)
    print("http://127.0.0.1:5000/nodes"+querystring)

    jsonResponse =  fetchNodes(querystring)

    lookupExistingNodes = {}
    
    for nodeResult in jsonResponse['nodes']:
        lookupExistingNodes[nodeResult[PROP_LABEL]] = nodeResult
        print('located host '+nodeResult[PROP_LABEL])

    #for now, only add hostnames to hosts already in project
    # todo: add cli option to specify whether new host IPs should be added to project
    '''
    newFolder = Node(TYPE_FOLDER)
    newFolder.Label = 'Amass Import '+argdata['filename'].split('/')[-1]
    newFolder.UID = 'newfolder_for_scan'
    newFolder.Parents.append(projectUID)
    '''
    
    for amassHost in allHosts:

        nodesToUpsert = [] #newFolder.convert()
        lookupExistingChildItems = {}
        childItemsToUpsert = []
        
        if amassHost.Label in lookupExistingNodes:
            amassHost.UID = lookupExistingNodes[amassHost.Label][PROP_UID]

            #fetch annotations for existing host
            querystring = '?uid={}&field={}&op={}&val={}&depth={}&type={}'.format(\
                amassHost.UID,\
                PROP_LASTMOD,\
                'gt',\
                0,\
                20,
                TYPE_ANNOTATION)
            print("http://127.0.0.1:5000/nodes"+querystring)

            
            jsonResponse =  fetchNodes(querystring)
            for nodeResult in jsonResponse['nodes']:
                if nodeResult[PROP_TYPE] in [TYPE_ANNOTATION]:
                    lookupExistingChildItems[nodeResult[PROP_TYPE]+'_'+nodeResult[PROP_LABEL]] = nodeResult
                    print('found existing: '+nodeResult[PROP_LABEL]+' '+nodeResult[PROP_UID])
                                
        else:
            continue
        '''
            amassHost.UID = amassHost.Label
            amassHost.Parents.append(newFolder.UID)
            print('host not found creating: '+amassHost.UID)
        '''

        print('AmassHost children count = '+str(len(amassHost.Children)))
        for childNode in amassHost.Children:
            print('childNode type: '+childNode.Type+' childNode Label:'+childNode.Label)
            tmpkey = childNode.Type+'_'+childNode.Label
            if tmpkey in lookupExistingChildItems:
                #childNode.UID = lookupExistingChildItems[tmpkey][PROP_UID]
                #ignore if hostname annotation already exists
                continue
            else:
                childNode.UID = amassHost.UID+'_'+childNode.Label
                childItemsToUpsert.append(childNode)
                print('annotation/port not existing, creating new UID: '+childNode.UID)
                #amassHost.Children.append
                        
            
        recursiveConvertNodesToAPIFormat(amassHost, nodesToUpsert)

        print(json.dumps(nodesToUpsert))
        serialisedJson = json.dumps(nodesToUpsert).encode('utf8')
        req = urllib.request.Request('http://127.0.0.1:5000/upsert', data=serialisedJson, headers={'content-type': 'application/json'})
        #response = urllib.request.urlopen(req)
        response = executeHttpRequest(req)
        print(response)
        '''
        if newFolder.UID == 'newfolder_for_scan':
           listOfUidsUpserted = json.loads(response.read().decode('utf8'))
           newFolder.UID = listOfUidsUpserted[0]
        '''
        
except Exception as e:
    print('an exception occurred during the attempted update: '+str(e))
    traceback.print_exc()
                
exit(0)


