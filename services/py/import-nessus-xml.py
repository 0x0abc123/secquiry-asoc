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
import html

C_USAGE = '''Usage: {0} <project-label> <nessus-xml-output-file>
        import a Nessus XML format (.nessus) file
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

        if not data['filename'].split('.')[-1].lower() in ['nessus']:
            print("nessus XML file required, got {}".format(data['filename']))
            raise Exception()

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
        
#instead of NodeWithChildren classes (as used in the .NET version), use a dict with an array of children:
# [{'host':hostNode, 'ports':[portNodes]},...]
# [{'port':portNode, 'textitems':[textNodes]},...]


argdata = parseArgs()

etree = ETree.parse(argdata['filename'])
root = etree.getroot()

#print("Root tag: {}".format(root.tag))
IgnoredPluginIDs = ['10180','10287','10919','11219','12053','19506','22964','25220','31422','39470','45590','50350','54615','110723','132634']
allHosts = []

reportElement = root.find('Report')
if not reportElement:
    print('The file does not appear to contain any report information')
    exit(0)

for host in reportElement.findall('ReportHost'):

    hname = host.attrib['name'].lower()

    print("Host: {}".format(host.attrib))
    #if not host.find('status').attrib['state'] == 'up':
    #    print('host is down')
    #    continue

    hostNode = Node(TYPE_HOST)
    allHosts.append(hostNode)

    annotationNodeHname = Node(TYPE_ANNOTATION)
    hostNode.Children.append(annotationNodeHname)
    annotationNodeHname.Label = '[name] '+hname
    
#    for hostchild in host:
#        print("    HostChild: <{}> {}".format(hostchild.tag,hostchild.attrib))

    #for hostname in host.find('hostnames').findall('hostname'):
    #    print("    Hostname: <{}> {}".format(hostname.tag,hostname.attrib))
    #    annotationNode = Node(TYPE_ANNOTATION)
    #    hostNode.Children.append(annotationNode)
    #    annotationNode.Label = '[name] '+hostname.attrib['name']

        
    tmpLabel = ''
    
    for tag in host.find('HostProperties').findall('tag'):
        print("    tag: {}".format(tag.attrib))
        annotationNode = Node(TYPE_ANNOTATION)
        if tag.attrib['name'] == 'host-rdns':
            annotationNode.Label = '[name] '+tag.text
        elif tag.attrib['name'] == 'host-ip':
            annotationNode.Label = '[addr] '+tag.text
            tmpLabel = tag.text
        if annotationNode.Label:
            hostNode.Children.append(annotationNode)

    if not tmpLabel:
        tmpLabel = str(uuid.uuid4())
    hostNode.Label = tmpLabel

    print('**Hostnode: {}'.format(hostNode.Label))
    for c in hostNode.Children:
        print('  **Annot: {}'.format(c.Label))


    portsDict = {}
    
    count = 0
    for reportitem in host.findall('ReportItem'):

        print("    ReportItem: {}".format(reportitem.attrib))
        if reportitem.attrib['pluginID'] not in IgnoredPluginIDs:

            portLabel = reportitem.attrib['port'] + '/' + reportitem.attrib['protocol'].lower()
            if portLabel != '0/tcp':
                portNode = portsDict[portLabel] if (portLabel in portsDict) else Node(TYPE_PORT)
                if not portNode.Label:
                    portNode.Label = portLabel
                    hostNode.Children.append(portNode)
                    portsDict[portLabel] = portNode
            '''
            portNode = portsDict[portLabel] if (portLabel in portsDict) else Node(TYPE_PORT)
            if not portNode.Label:
                portNode.Label = portLabel
                hostNode.Children.append(portNode)
                portsDict[portLabel] = portNode
            '''
            
            itemLabel = str(4 - int(reportitem.attrib['severity']))+' '+reportitem.attrib['pluginName']
            body = ''

            synopsisElement = reportitem.find('synopsis')
            body += '[Synopsis]:\n'+synopsisElement.text+'\n\n' if not (synopsisElement is None) else ''
            print('synopsis: '+synopsisElement.text)
            
            cvssElement = reportitem.find('cvss3_base_score')
            body += '[CVSS Base Score]:\n'+cvssElement.text+'\n\n' if not (cvssElement is None) else ''

            descriptionElement = reportitem.find('description')
            body += '[Description]:\n'+descriptionElement.text+'\n\n' if not (descriptionElement is None) else ''

            outputElement = reportitem.find('plugin_output')
            body += '[Plugin Output]:\n'+html.unescape(outputElement.text)+'\n\n' if not (outputElement is None) else ''

            solutionElement = reportitem.find('solution')
            body += '[Solution]:\n'+solutionElement.text+'\n\n' if not (solutionElement is None) else ''

            body = body.strip()

            textNode = Node(TYPE_TEXT)
            if portLabel != '0/tcp':
                portNode.Children.append(textNode)
            else:
                hostNode.Children.append(textNode)
            '''
            portNode.Children.append(textNode)
            '''
            textNode.TextData = body
            textNode.Label = itemLabel
            print('create node: '+textNode.Label)
            textNode.Detail = '{}:{} nessus plugin'.format(hostNode.Label, portLabel)

    for c in hostNode.Children:
        c.Detail = '{} (nessus {})'.format(hostNode.Label, argdata['projectname'])


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

    newFolder = Node(TYPE_FOLDER)
    newFolder.Label = 'Nessus Import '+argdata['filename'].split('/')[-1]
    newFolder.UID = 'newfolder_for_scan'
    newFolder.Parents.append(projectUID)

    for nessusHost in allHosts:

        hostsAddedToNewFolder = False
        nodesToUpsert = []
        lookupExistingChildItems = {}

        if nessusHost.Label in lookupExistingNodes:
            nessusHost.UID = lookupExistingNodes[nessusHost.Label][PROP_UID]

            #fetch ports for existing host
            querystring = '?uid={}&field={}&op={}&val={}&depth={}'.format(\
                nessusHost.UID,\
                PROP_LASTMOD,\
                'gt',\
                0,\
                20)
            print("http://127.0.0.1:5000/nodes"+querystring)

            
            jsonResponse =  fetchNodes(querystring)
            for nodeResult in jsonResponse['nodes']:
                if nodeResult[PROP_TYPE] in [TYPE_PORT, TYPE_ANNOTATION]:
                    lookupExistingChildItems[nodeResult[PROP_TYPE]+'_'+nodeResult[PROP_LABEL]] = nodeResult
                    print('found existing: '+nodeResult[PROP_LABEL]+' '+nodeResult[PROP_UID])
                                
        else:
            nessusHost.UID = nessusHost.Label
            nessusHost.Parents.append(newFolder.UID)
            hostsAddedToNewFolder = True
            print('host not found creating: '+nessusHost.UID+' under newFolder '+newFolder.UID)

        print('NessusHost children count = '+str(len(nessusHost.Children)))
        for childNode in nessusHost.Children:
            print('childNode type: '+childNode.Type+' childNode Label:'+childNode.Label)
            tmpkey = childNode.Type+'_'+childNode.Label
            if tmpkey in lookupExistingChildItems:
                childNode.UID = lookupExistingChildItems[tmpkey][PROP_UID]
            else:
                childNode.UID = nessusHost.UID+'_'+childNode.Label
                print('annotation/port not existing, creating new UID: '+childNode.UID)
                #nessusHost.Children.append
            
            ccount = 0
            for c in childNode.Children:
                ccount += 1
                print('text/annotations[] for port/annotation='+childNode.Label+' * port/annotaitonType='+childNode.Type+' '+str(ccount)+'/'+str(len(childNode.Children)))
            
            for grandChildNode in childNode.Children:
                grandChildNode.UID = childNode.UID+'_'+grandChildNode.Label
                print('text/annotation creating: Type='+grandChildNode.Type+' child UID='+childNode.UID+', grandchild Label='+grandChildNode.Label)
            
            
        recursiveConvertNodesToAPIFormat(nessusHost, nodesToUpsert)
        if hostsAddedToNewFolder:
            nodesToUpsert.insert(0,newFolder.convert())

        print(json.dumps(nodesToUpsert))
        serialisedJson = json.dumps(nodesToUpsert).encode('utf8')
        req = urllib.request.Request('http://127.0.0.1:5000/upsert', data=serialisedJson, headers={'content-type': 'application/json'})
        #response = urllib.request.urlopen(req)
        response = executeHttpRequest(req)
        print(response)
        if hostsAddedToNewFolder and newFolder.UID == 'newfolder_for_scan':
           listOfUidsUpserted = json.loads(response.read().decode('utf8'))
           newFolder.UID = listOfUidsUpserted[0]

        
except Exception as e:
    print('an exception occurred during the attempted update: '+str(e))
    traceback.print_exc()
                
exit(0)


