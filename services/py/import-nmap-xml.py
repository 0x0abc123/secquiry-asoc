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

C_USAGE = '''Usage: {0} <project-label> <nmap-xml-output-file>
        import an Nmap XML format file
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

        if not data['filename'].split('.')[-1].lower() in ['xml']:
            print("XML file required, got {}".format(data['filename']))
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
        
#instead of NodeWithChildren classes, use a dict with an array of children:
# [{'host':hostNode, 'ports':[portNodes]},...]
# [{'port':portNode, 'textitems':[textNodes]},...]


argdata = parseArgs()

etree = ETree.parse(argdata['filename'])
root = etree.getroot()

#print("Root tag: {}".format(root.tag))

allHosts = []

for host in root.findall('host'):

    print("Host: {}".format(host.attrib))
    if not host.find('status').attrib['state'] == 'up':
        print('host is down')
        continue

    hostNode = Node(TYPE_HOST)
    allHosts.append(hostNode)
    
#    for hostchild in host:
#        print("    HostChild: <{}> {}".format(hostchild.tag,hostchild.attrib))

    for hostname in host.find('hostnames').findall('hostname'):
        print("    Hostname: <{}> {}".format(hostname.tag,hostname.attrib))
        annotationNode = Node(TYPE_ANNOTATION)
        hostNode.Children.append(annotationNode)
        annotationNode.Label = '[name] '+hostname.attrib['name'].lower()
        
    tmpIPv6Addr = ''
    tmpMACAddr = ''
    tmpLabel = ''
    
    for address in host.findall('address'):
        print("    Address: {}".format(address.attrib))
        annotationNode = Node(TYPE_ANNOTATION)
        hostNode.Children.append(annotationNode)
        annotationNode.Label = '[addr] '+address.attrib['addr']
        if 'vendor' in address.attrib:
            annotationNode.Detail = '[vendor] '+address.attrib['vendor']
        if address.attrib['addrtype'] == 'ipv4':
            tmpLabel = address.attrib['addr']
        elif address.attrib['addrtype'] == 'ipv6' and not tmpLabel:
            tmpIPv6Addr = address.attrib['addr']
        elif address.attrib['addrtype'] == 'mac' and not tmpLabel:
            tmpMACAddr = address.attrib['addr']
        if not tmpLabel:
            tmpLabel = tmpIPv6Addr if tmpIPv6Addr else (tmpMACAddr if tmpMACAddr else str(uuid.uuid4()))
        hostNode.Label = tmpLabel

    count = 0
    hostports = host.find('ports')
    if hostports:
        for port in hostports.findall('port'):

            print("    Port: {}".format(port.attrib))
            if port.find('state').attrib['state'] == 'open':

                portNode = Node(TYPE_PORT)
                hostNode.Children.append(portNode)

                portNode.Label = port.attrib['portid'] + '/' + port.attrib['protocol']

                service = port.find('service')
                if not service:
                    continue

                print("         Service: {}".format(service.attrib))

                body = ''
                body += service.attrib['product']+' ' if 'product' in service.attrib else ''
                body += service.attrib['version']+' ' if 'version' in service.attrib else ''
                body += service.attrib['extrainfo']+' ' if 'extrainfo' in service.attrib else ''
                body += service.attrib['ostype']+' ' if 'ostype' in service.attrib else ''
                body = body.strip()

                UNKNOWN_SERVICE = 'Unknown Service'
                if not body:
                    body = UNKNOWN_SERVICE
                
                for script in port.findall('script'):
                    print("         Script: {}".format(script.attrib))
                    scriptName = 'NSE Script: '+(script.attrib['id'] if script.attrib['id'] else '<?>')
                    body += '\n\n'+scriptName+'\n'+'-'*len(scriptName)+'\nOutput:\n'
                    for elem in script.findall('elem'):
                        print("           Elem: {}, text: {}".format(elem.attrib, elem.text))
                        if 'key' in elem.attrib and elem.text:
                            body += elem.attrib['key'] + ': ' + elem.text + '\n'
                    for table in script.findall('table'):
                        for telem in table.findall('elem'):
                            #print("           TElem: {}, text: {}".format(telem.attrib, telem.text))
                            te_key = telem.attrib['key'] if 'key' in telem.attrib else ''
                            te_text = telem.text if telem.text else ''
                            body += ' [*] '+ te_key + ': ' + te_text + '\n'
                    
                    
                count += 1
                if body != UNKNOWN_SERVICE:
                    textNode = Node(TYPE_TEXT)
                    portNode.Children.append(textNode)
                    textNode.TextData = body
                    textNode.Label = "NMAP scan "+portNode.Label
                    print('create node: '+str(count)+' '+textNode.Label)
                else:
                    annotationNode = Node(TYPE_ANNOTATION)
                    portNode.Children.append(annotationNode)
                    annotationNode.Label = '(unknown service)'
                    print('create annotation: '+str(count)+' '+annotationNode.Label)

                for c in portNode.Children:
                    c.Detail = '{}:{} nmap script'.format(hostNode.Label, portNode.Label)

    for c in hostNode.Children:
        c.Detail = '{} (nmap {})'.format(hostNode.Label, argdata['projectname'])
                

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
    #def fetchNodes(query):
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
    newFolder.Label = 'Nmap Import '+argdata['filename'].split('/')[-1]
    newFolder.UID = 'newfolder_for_scan'
    newFolder.Parents.append(projectUID)

    for nmapHost in allHosts:

        hostsAddedToNewFolder = False
        nodesToUpsert = []
        lookupExistingChildItems = {}

        if nmapHost.Label in lookupExistingNodes:
            nmapHost.UID = lookupExistingNodes[nmapHost.Label][PROP_UID]

            #fetch ports for existing host
            querystring = '?uid={}&field={}&op={}&val={}&depth={}'.format(\
                nmapHost.UID,\
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
            nmapHost.UID = nmapHost.Label
            nmapHost.Parents.append(newFolder.UID)
            hostsAddedToNewFolder = True
            print('host not found creating: '+nmapHost.UID)

        print('NmapHost children count = '+str(len(nmapHost.Children)))
        for childNode in nmapHost.Children:
            print('childNode type: '+childNode.Type+' childNode Label:'+childNode.Label)
            tmpkey = childNode.Type+'_'+childNode.Label
            if tmpkey in lookupExistingChildItems:
                childNode.UID = lookupExistingChildItems[tmpkey][PROP_UID]
            else:
                childNode.UID = nmapHost.UID+'_'+childNode.Label
                print('annotation/port not existing, creating new UID: '+childNode.UID)
                #nmapHost.Children.append
            
            ccount = 0
            for c in childNode.Children:
                ccount += 1
                print('text/annotations[] for port/annotation='+childNode.Label+' * port/annotaitonType='+childNode.Type+' '+str(ccount)+'/'+str(len(childNode.Children)))
            
            for grandChildNode in childNode.Children:
                grandChildNode.UID = childNode.UID+'_'+grandChildNode.Label
                print('text/annotation creating: Type='+grandChildNode.Type+' child UID='+childNode.UID+', grandchild Label='+grandChildNode.Label)
            
            
        recursiveConvertNodesToAPIFormat(nmapHost, nodesToUpsert)
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


