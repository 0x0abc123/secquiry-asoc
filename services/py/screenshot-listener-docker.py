#!/usr/bin/env python3
#import http.server
#import socketserver

import json

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

import random
import sys
import re
import os
import time

import copy
import datetime
import uuid
import urllib.request
import urllib.parse
import traceback
import ssl

import io
import mimetypes
import base64

######################################################
'''
docker pull selenium/standalone-firefox
#!/bin/bash
docker run -d -p 127.0.0.1:4444:4444 -p 127.0.0.1:7900:7900 -v /dev/shm:/dev/shm selenium/standalone-firefox

Notes:
* There needs to be a ReportTemplate.docx in the current folder, 
* custom styles should be saved into the docx, along with headers, footers, a title page
* the auto generated content will be appended to anything that is in the template

TODO:
make this a microservice/daemon that polls the database for report nodes,
    if a report node has an annotation (eg. 'generate') then do the auto generation, 
    upload the report as a file attachment to the report node
    delete the annotation (create a folder called 'completed jobs' and move it there or maybe just the recycle bin)
'''
######################################################

C_USAGE = '''Usage: {0} <projectname> <reportname>
        generate a docx report
'''

#COLLABLIO_HOST = 'http://127.0.0.1:5000'
COLLABLIO_HOST = 'http://10.3.3.60:5000'

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
TYPE_JOBREQ = "Job Request"


DAEMON_LISTENER_MODE = False

def parseArgs():
    global DAEMON_LISTENER_MODE
    data = {}
    try:
        num_args = len(sys.argv)
        data['projectname'] = sys.argv[1]
        data['reportname'] = sys.argv[2]
    except:
        print(C_USAGE.format(sys.argv[0]))
        if not 'projectname' in data:
            exit(0)

    #start in autogenerator listen mode
    DAEMON_LISTENER_MODE = not (('projectname' in data) and ('reportname' in data))
    return data

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
    req = urllib.request.Request(COLLABLIO_HOST+"/nodes"+query)
    response = executeHttpRequest(req)
    #def fetchNodes(query):
    #response = urllib.request.urlopen(COLLABLIO_HOST+"/nodes"+query)
    jsonResponse =  json.loads(response.read().decode('utf8'))
    if 'nodes' not in jsonResponse:
        raise Exception()
    return jsonResponse


def recursiveConvertNodesToAPIFormat(node, listToAddTheNodeTo):
    listToAddTheNodeTo.append(node.convert())
    if node.Children:
        for child in node.Children:
            recursiveConvertNodesToAPIFormat(child, listToAddTheNodeTo)
        




class MultiPartForm:
    """Accumulate the data to be used when posting a form."""

    def __init__(self):
        self.form_fields = []
        self.files = []
        # Use a large random byte string to separate
        # parts of the MIME data.
        self.boundary = uuid.uuid4().hex.encode('utf-8')
        return

    def get_content_type(self):
        return 'multipart/form-data; boundary={}'.format(
            self.boundary.decode('utf-8'))

    def add_field(self, name, value):
        """Add a simple field to the form data."""
        self.form_fields.append((name, value))

    def add_file(self, fieldname, filename, fileHandle,
                 mimetype=None):
        """Add a file to be uploaded."""
        body = fileHandle.read()
        if mimetype is None:
            mimetype = (
                mimetypes.guess_type(filename)[0] or
                'application/octet-stream'
            )
        self.files.append((fieldname, filename, mimetype, body))
        return

    @staticmethod
    def _form_data(name):
        return ('Content-Disposition: form-data; '
                'name="{}"\r\n').format(name).encode('utf-8')

    @staticmethod
    def _attached_file(name, filename):
        #return ('Content-Disposition: file; '
        return ('Content-Disposition: form-data; '
                'name="{}"; filename="{}"\r\n').format(
                    name, filename).encode('utf-8')

    @staticmethod
    def _content_type(ct):
        return 'Content-Type: {}\r\n'.format(ct).encode('utf-8')

    def __bytes__(self):
        """Return a byte-string representing the form data,
        including attached files.
        """
        buffer = io.BytesIO()
        boundary = b'--' + self.boundary + b'\r\n'

        # Add the form fields
        for name, value in self.form_fields:
            buffer.write(boundary)
            buffer.write(self._form_data(name))
            buffer.write(b'\r\n')
            buffer.write(value.encode('utf-8'))
            buffer.write(b'\r\n')

        # Add the files to upload
        for f_name, filename, f_content_type, body in self.files:
            buffer.write(boundary)
            buffer.write(self._attached_file(f_name, filename))
            buffer.write(self._content_type(f_content_type))
            buffer.write(b'\r\n')
            buffer.write(body)
            buffer.write(b'\r\n')

        buffer.write(b'--' + self.boundary + b'--\r\n')
        return buffer.getvalue()
        


def sortNodes(uidDict):
    return getNodeForUID(uidDict[PROP_UID])[PROP_LABEL]
    


NODE_INDEX = {'_':''}

def getNodeForUID(uid):
    global NODE_INDEX    
    node = NODE_INDEX[uid] if uid in NODE_INDEX else None
    return node

def storeNode(node):
    global NODE_INDEX
    NODE_INDEX[node[PROP_UID]] = node

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

def fetchNodesPost(uids = [], field = PROP_LASTMOD, op = 'gt', val = '0', depth = 20, typ = ''):

    reqdata = { 'uids': uids, 'field': field, 'op': op, 'val': val, 'depth': depth, 'type': typ }
    print(json.dumps(reqdata))
    req = urllib.request.Request(url=COLLABLIO_HOST+'/nodes', data=bytes(json.dumps(reqdata), encoding='utf-8'))
    req.add_header('Content-Type', 'application/json')
    #response = urllib.request.urlopen(req)
    response = executeHttpRequest(req)
    jsonResponse =  json.loads(response.read().decode('utf8'))
    if 'nodes' not in jsonResponse:
        raise Exception()
    return jsonResponse

def moveNodesPost(moveData):

    print(json.dumps(moveData))
    req = urllib.request.Request(url=COLLABLIO_HOST+'/move', data=bytes(json.dumps(moveData), encoding='utf-8'))
    req.add_header('Content-Type', 'application/json')
    #response = urllib.request.urlopen(req)
    response = executeHttpRequest(req)
    jsonResponse =  json.loads(response.read().decode('utf8'))
    return jsonResponse

def getRecycleBinFolderUID():
    querystring = '?uid={}&field={}&op={}&val={}&depth={}&type={}'.format(\
        '',\
        PROP_LABEL,\
        'eq',\
        urllib.parse.quote('Recycle Bin'),\
        20,\
        TYPE_FOLDER)
    print(COLLABLIO_HOST+"/nodes"+querystring)

    try:
        jsonResponse =  fetchNodes(querystring)
        return jsonResponse['nodes'][0][PROP_UID]
    except:
        print('recycle bin folder doesnt exist, creating a new one')

    try:
        newRecycleBinNode = Node(TYPE_FOLDER)
        newRecycleBinNode.Label = 'Recycle Bin'
        nodesToUpsert = []
        recursiveConvertNodesToAPIFormat(newRecycleBinNode, nodesToUpsert)
        serialisedJson = json.dumps(nodesToUpsert).encode('utf8')
        req = urllib.request.Request(COLLABLIO_HOST+'/upsert', data=serialisedJson, headers={'content-type': 'application/json'})
        #response = urllib.request.urlopen(req)
        response = executeHttpRequest(req)
        returnedUids = json.loads(response.read().decode('utf8'))
        return returnedUids[0]
    except Exception as e:
        print('an exception occurred while creating recycle bin: '+str(e))
        traceback.print_exc()

SCREENSHOTFILE_PREFIX = 'SCR_'
HTTPTIMEOUT=5
def generateScreenshotForPortNode(portNode):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        #query recursively to find all child nodes under report node
        hostNode = getNodeForUID(portNode[PROP_PARENTLIST][0][PROP_UID])
        #print('generateScreenshotForPortNode: '+str(hostNode[HOSTNAMES]))
        portLabel = portNode[PROP_LABEL]
        if portLabel.endswith('/tcp'):
            portNum = portLabel.split('/')[0]
            tmpHostnames = []
            for hostnameNode in hostNode[HOSTNAMES]:
                tmpHostnames.append(hostnameNode)
            #really need to fix this to check the label to see if it's an IPv4 or IPv6 address
            if len(tmpHostnames) < 1:
                tmpHostnames.append(hostNode[PROP_LABEL])

            for hostname in tmpHostnames:
                httpURL = 'http://{}:{}'.format(hostname,portNum)
                httpsURL = 'https://{}:{}'.format(hostname,portNum)
                orderToTry = [httpsURL, httpURL] if (portNum in ['443','4443','8443','9443']) else [httpURL, httpsURL]
                for theURL in orderToTry:
                    print('GET: '+theURL)
                    try:
                        res  = urllib.request.urlopen(url=theURL,timeout=HTTPTIMEOUT,context=ctx)
                        #res  = executeHttpRequest(url=theURL,timeout=HTTPTIMEOUT,context=ctx)
                    except Exception as e:
                        if not (type(e) is urllib.error.HTTPError):
                            continue
                    try:
                        driver.get(theURL)
                        time.sleep(5.0)
                        baseoutputfilename = SCREENSHOTFILE_PREFIX+portNum+theURL.split('.')[0].replace(':','_').replace('/','')
                        #pagesource = (str(driver.page_source))
                        filename = baseoutputfilename+".png"
                        driver.save_screenshot('./'+filename)
                        #with open('./'+baseoutputfilename+'.html.txt', 'w') as fO:
                        #    fO.write(pagesource)
                        #    fO.close()
                        return filename
                    except:
                        continue
        
        return ''
    except Exception as e:
        print('an exception occurred while generating the report: '+str(e))
        traceback.print_exc()
        return ''



##################################################################################
## The main program
##################################################################################


argdata = parseArgs()

#QueryNodesGet(string uid = null, string field=null, string op=null, string val=null, int depth = 0, string type = null)

profile = webdriver.FirefoxProfile()

PROXY_HOST = "192.168.12.1"
PROXY_PORT = "8000"
#profile.set_preference("network.proxy.type", 1)
#profile.set_preference("network.proxy.http", PROXY_HOST)
#profile.set_preference("network.proxy.http_port", int(PROXY_PORT))
profile.set_preference("dom.webdriver.enabled", False)
profile.set_preference('useAutomationExtension', False)
profile.update_preferences()
desired = webdriver.DesiredCapabilities.FIREFOX

profile.accept_untrusted_certs = True

#driver = webdriver.Firefox(firefox_profile=profile, desired_capabilities=desired)
driver = webdriver.Remote(
   command_executor='http://127.0.0.1:4444/wd/hub',
   desired_capabilities=DesiredCapabilities.FIREFOX, browser_profile=profile)

#driver = webdriver.Firefox(firefox_profile=profile)

#query to find projectname data['projectname']

projectUID = ''

querystring = '?uid=&field={}&op={}&val={}&depth={}&type={}'.format(\
    PROP_LABEL,\
    'eq',\
    urllib.parse.quote(argdata['projectname']),\
    20,\
    TYPE_PROJECT)
print(COLLABLIO_HOST+"/nodes"+querystring)

try:
    jsonResponse =  fetchNodes(querystring)
    for nodeResult in jsonResponse['nodes']:
        if nodeResult[PROP_LABEL] == argdata['projectname']:
            projectUID = nodeResult[PROP_UID]
            break
    print('located project '+projectUID)
except Exception as e:
    print('an exception occurred while generating the report: '+str(e))
    traceback.print_exc()


if not DAEMON_LISTENER_MODE:

    try:

        #query recursively to find the specified reportname under projectname
        querystring = '?uid={}&field={}&op={}&val={}&depth={}&type={}'.format(\
            projectUID,\
            PROP_LABEL,\
            'eq',\
            urllib.parse.quote(argdata['reportname']),\
            20,\
            TYPE_REPORT)
        print(COLLABLIO_HOST+"/nodes"+querystring)

        jsonResponse =  fetchNodes(querystring)

        reportRootNode = None
        for nodeResult in jsonResponse['nodes']:
            if nodeResult[PROP_LABEL] == argdata['reportname']:
                reportRootNode = nodeResult

        if not reportRootNode:
            print('unable to locate report: '+argdata['reportname'])
            exit(0)

        print('located report '+argdata['reportname'])

        generateReportForReportNode(reportRootNode)

    except Exception as e:
        print('an exception occurred while generating the report: '+str(e))
        traceback.print_exc()
    
    exit(0)




print('No project or filename arguments were provided. Running in Daemon Listener Mode')

#query to find all new reports since last check
# todo: save the last check time in persistent storage to avoid fetching every single report upon the process running

REFRESH_INTERVAL = 30.0

LASTCHECKED = 'lastchecked'
HOSTNAMES = 'hostnames'

lastFetchTime = 0
sleepTime = REFRESH_INTERVAL
uidsOfHosts = set()

while True:
    querystring = '?uid={}&field={}&op={}&val={}&depth={}&type={}'.format(\
        projectUID,\
        PROP_LASTMOD,\
        'gt',\
        '__LASTMODTIME__',\
        20,\
        TYPE_HOST)
    print('*'*30)
    querystring = querystring.replace('__LASTMODTIME__',str(lastFetchTime))
    print(COLLABLIO_HOST+"/nodes"+querystring)    

    try:
        jsonResponse =  fetchNodes(querystring)
        print(json.dumps(jsonResponse))
        
        if not 'nodes' in jsonResponse:
            continue

        #    time.sleep(1)
        numHosts = len(jsonResponse['nodes'])
        sleepTime = REFRESH_INTERVAL / numHosts if numHosts else REFRESH_INTERVAL
        
        if 'timestamp' in jsonResponse:
            lastFetchTime = int(jsonResponse['timestamp'])
            print('(cur)lastfetchtime='+str(lastFetchTime)+', str(int(jsonResponse[timestamp])='+str(int(jsonResponse['timestamp'])))

        #clearNodeIndex()
        
        #uidsOfHosts = []
        for nodeResult in jsonResponse['nodes']:
            if nodeResult[PROP_TYPE] == TYPE_HOST:
                #uidsOfHosts.append(nodeResult[PROP_UID])
                uidsOfHosts.add(nodeResult[PROP_UID])
                #nodeResult.lastChecked = 0
                #nodeResult.hostnames = set()
                nodeResult[LASTCHECKED] = 0
                nodeResult[HOSTNAMES] = set()
                storeNode(nodeResult)

        # now query the database for report generation jobrequests pending for any of those report nodes 
        #jsonResponse = fetchNodesPost(uids = uidsOfHosts, typ = TYPE_JOBREQ)
        for hostUID in list(uidsOfHosts):
        
            hostNode = getNodeForUID(hostUID)
            hostLastCheckedTimestamp = hostNode[LASTCHECKED]
            jsonResponse = fetchNodesPost(uids = [hostUID], field = PROP_LASTMOD, op = 'gt', val = str(hostLastCheckedTimestamp), depth = 20)
            print('LOOKIE HERE ***********************************')
            print(jsonResponse)
            hostNode[LASTCHECKED] = int(jsonResponse['timestamp'])

            portNodes = []
            
            HOSTNAME_PREFIX = '[name] '
            
            for nodeResult in jsonResponse['nodes']:
            
                print(str(nodeResult))
                if nodeResult[PROP_TYPE] == TYPE_PORT:
                    portNodes.append(nodeResult)
                elif nodeResult[PROP_TYPE] == TYPE_ANNOTATION and nodeResult[PROP_LABEL].startswith(HOSTNAME_PREFIX):
                    hostNode[HOSTNAMES].add(nodeResult[PROP_LABEL][len(HOSTNAME_PREFIX):])
                    print('adding hostname: '+nodeResult[PROP_LABEL][len(HOSTNAME_PREFIX):])
                else:
                    continue

            for portNode in portNodes:

                portNode[PROP_PARENTLIST] = [{PROP_UID : hostUID}]
                portUID = portNode[PROP_UID] #nodeResult[PROP_PARENTLIST][0][PROP_UID]
                if not getNodeForUID(portUID):
                    #need to persist a list of port/host UIDs on the filesystem so that everything doesnt get screenshotted again every startup
                    #or since we're fetching the tree of nodes underneath the host, we can just check whether there's a screenshot file already attached to the port
                    storeNode(portNode)

                    screenshotfile = None
                    try:
                        screenshotfile = generateScreenshotForPortNode(portNode)
                    except Exception as se:
                        print('an exception occurred while attempting to screenshot: '+str(se))
                        traceback.print_exc()
                        continue
                    if screenshotfile:
                        print('about to upload '+screenshotfile)
                        #apparently python3 urllib doesn't have builtin support for multipart/form-data
                        # there's an implementation here https://pymotw.com/3/urllib.request/
                        
                        params = { 'parentid': portNode[PROP_UID] }

                        # Create the form with simple fields
                        form = MultiPartForm()
                        form.add_field('type', 'file_upload')
                        form.add_field('_p', json.dumps(params))

                        # Add the file
                        form.add_file('filedata', screenshotfile, fileHandle=open(screenshotfile, "rb"))

                        # Build the request, including the byte-string
                        # for the data to be posted.
                        data = bytes(form)
                        r = urllib.request.Request(COLLABLIO_HOST+'/upload', data=data) #  'http://127.0.0.1:9123'

                        r.add_header('Content-type', form.get_content_type())
                        r.add_header('Content-length', len(data))

                        print()
                        print('OUTGOING DATA:')
                        for name, value in r.header_items():
                            print('{}: {}'.format(name, value))

                        #print(r.data.decode('utf-8'))

                        #respStr = urllib.request.urlopen(r).read().decode('utf-8')
                        respStr = executeHttpRequest(r).read().decode('utf-8')
                        print('SERVER RESPONSE:')
                        print(respStr)

                        #delete the local report file
                        os.remove(screenshotfile)
            

    except Exception as e:
        print('an exception occurred while fetching the report/job nodes: '+str(e))
        traceback.print_exc()
        sleepTime = REFRESH_INTERVAL
    time.sleep(sleepTime)
      

driver.close()      
exit(0)




    
'''
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import random

driver = webdriver.Firefox()

with open('./input_urls.txt', 'r') as fB:
    inbufferB = fB.readlines()
    fB.close()
    for line in inbufferB:
        try:
            url = line.strip()
            driver.get(url)
            time.sleep(5.0)
            baseoutputfilename = url.replace(':','_').replace('/','_').replace('?','_').replace('&','_').replace('=','_').replace('+','_').replace('%','_')
            pagesource = (str(driver.page_source))
            driver.save_screenshot('./'+baseoutputfilename+".png")
            with open('./'+baseoutputfilename+'.html.txt', 'w') as fO:
                fO.write(pagesource)
                fO.close()
        except:
            pass
driver.close()
'''
