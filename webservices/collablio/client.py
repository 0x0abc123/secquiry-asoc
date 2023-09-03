import os
import re
import copy
import datetime
import sys
import uuid
import urllib.request
import urllib.error
import urllib.parse
import time
from shutil import copyfileobj
import json
import traceback
import collablio.node as cnode
import appconfig
import io
import mimetypes
import secretstore
import tempfile

COLLABLIO_HOST = appconfig.getValue('collablio_url') #"http://127.0.0.1:5000"

class Client:

    def __init__(self, _auth_token_hdr_val = None, hostURL = None):
        self.auth_token_hdr_val = _auth_token_hdr_val
        self.host_url = hostURL if hostURL is not None else COLLABLIO_HOST
        self.user = ''
        self.passwd = ''
        self.lastAuthTime = datetime.datetime(1970,1,1)

    def setCreds(self, username, password):
        self.user = username
        self.passwd = password
    
    def getAuthToken(self):
        mins90 = datetime.timedelta(minutes=90)
        now = datetime.datetime.now()
        if not self.auth_token_hdr_val or self.lastAuthTime + mins90 < now:
            self.auth_token_hdr_val = self.LoginAndGetToken(self.user, self.passwd)
            self.lastAuthTime = now
        return self.auth_token_hdr_val

    def executeHttpRequest(self, request):
        retries = 3
        while retries > 0:
            if self.user != '' and self.passwd != '':
                self.getAuthToken()
            request.headers['Authorization'] = f'Bearer {self.auth_token_hdr_val}'
            try:
                response = urllib.request.urlopen(request)
                return response
            except urllib.error.HTTPError as error:
                if error.code > 400:
                    time.sleep(1)
                    self.auth_token_hdr_val = None
                    retries -= 1
                    continue
                return None
        return None
        
    def fetchNodesRequest(self, querystring):
        req = urllib.request.Request(self.host_url+"/nodes"+querystring)
        response = self.executeHttpRequest(req)
        jsonResponse =  json.loads(response.read().decode('utf8'))
        if 'nodes' not in jsonResponse:
            jsonResponse = {'nodes':[]}
        return jsonResponse

    def fetchNodes(self, uid = '', field = cnode.PROP_LASTMOD, op = 'gt', val = '0', depth = 20, ntype = '', body = False):
        querystring = f'?uid={uid}&field={field}&op={op}&val={val}&depth={depth}&type={ntype}'
        if body:
            querystring += '&body=true'
        return self.fetchNodesRequest(querystring)

    def fetchNodesPostObj(self, postdata):
        #reqdata = { 'uids': uids, 'field': field, 'op': op, 'val': val, 'depth': depth, 'type': typ }
        req = urllib.request.Request(url=self.host_url+'/nodes', data=bytes(json.dumps(postdata), encoding='utf-8'))
        req.add_header('Content-Type', 'application/json')
        response = self.executeHttpRequest(req)
        jsonResponse =  json.loads(response.read().decode('utf8'))
        return jsonResponse

    def fetchNodesPost(self, uids = [], field = cnode.PROP_LASTMOD, op = 'gt', val = '0', depth = 20, typ = ''):
        reqdata = { 'uids': uids, 'field': field, 'op': op, 'val': val, 'depth': depth, 'type': typ }        
        return self.fetchNodesPostObj(reqdata)

    def moveNodesPostObj(self, postdata):
        #reqdata = { 'uids': uids, 'field': field, 'op': op, 'val': val, 'depth': depth, 'type': typ }
        req = urllib.request.Request(url=self.host_url+'/move', data=bytes(json.dumps(postdata), encoding='utf-8'))
        req.add_header('Content-Type', 'application/json')
        response = self.executeHttpRequest(req)
        jsonResponse =  json.loads(response.read().decode('utf8'))
        return jsonResponse


    # nodesToUpsert is a list of collablio.node.Node
    def upsertNodesPostObj(self, nodeslist):
        serialisedJson = json.dumps(nodeslist).encode('utf8')
        req = urllib.request.Request(self.host_url+'/upsert', data=serialisedJson, headers={'content-type': 'application/json'})
        #response = urllib.request.urlopen(req)
        response = self.executeHttpRequest(req)
        # should return list of uids
        new_uids = json.loads(response.read().decode('utf8'))
        return new_uids
        
    def upsertNodes(self, nodesToUpsert, convertToAPIFormat = True):
        apiNodesList = [] if convertToAPIFormat else nodesToUpsert
        if convertToAPIFormat:
            for cNode in nodesToUpsert:
                cnode.recursiveConvertNodesToAPIFormat(cNode, apiNodesList)
        return self.upsertNodesPostObj(apiNodesList)

    def createFileNode(self, multipartform, api_path='/upload'):
        # Build the request, including the byte-string
        # for the data to be posted.
        data = bytes(multipartform)
        r = urllib.request.Request(self.host_url+api_path, data=data) #  'http://127.0.0.1:9123'

        r.add_header('Content-type', multipartform.get_content_type())
        r.add_header('Content-length', len(data))

        return self.executeHttpRequest(r).read().decode('utf-8')
    
    def downloadFile(self, uid):
        req = urllib.request.Request(self.host_url+"/authddownload/"+uid)
        response = self.executeHttpRequest(req)
        #print(response.headers)
        #jsonResponse =  json.loads(response.read().decode('utf8'))
        #out_file = tempfile.SpooledTemporaryFile(max_size=1048576)
        filename = uid
        cdisp = response.headers.get("Content-Disposition")
        if cdisp is not None:
            filename += "-"+cdisp.split("=")[-1]
        tmpfilepath = os.path.join(tempfile.gettempdir(),filename)
        out_file = open(tmpfilepath,"wb")
        copyfileobj(response, out_file)
        out_file.close()
        return (tmpfilepath, response.headers.get('content-type'), cdisp)

    def LoginAndGetToken(self, username, password):
        loginData = {'username':username,'password':password}
        serialisedJson = json.dumps(loginData).encode('utf8')
        req = urllib.request.Request(self.host_url+'/login', data=serialisedJson, headers={'content-type': 'application/json'})
        response = urllib.request.urlopen(req)
        # should return list of uids
        responsedata = json.loads(response.read().decode('utf8'))
        return responsedata['token']
        
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
        
sstore = secretstore.GetStore()
client = Client()
client.setCreds(sstore.get('secquiry_user'),sstore.get('secquiry_pass'))
