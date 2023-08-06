# uvicorn main:app --port 8800

from fastapi import FastAPI, Header, Depends, HTTPException, UploadFile, Form, Request, Response, status
from fastapi.responses import StreamingResponse
import importers
import generators
import importlib
import json
import multiprocessing
import tasksched
import notifier
import logger
import appconfig
import authhelpers
import collablio.client as cclient
import collablio.node as cnode

app = FastAPI()

# launch tasksched
t_tasksched = multiprocessing.Process(target=tasksched.run)
t_tasksched.start()

# launch notifier
t_notifier = multiprocessing.Process(target=notifier.run)
t_notifier.start()

# load plugins
# importers
Importers = {}

for m in importers.__all__:
  try:
    importer_module = importlib.import_module('importers.'+m)
    Importers[m] = importer_module
    logger.logEvent(f'module: {m}')
  except Exception as e:
    logger.logEvent(str(e))

logger.logEvent(Importers)

# generators
Generators = {}

for m in generators.__all__:
  try:
    generator_module = importlib.import_module('generators.'+m)
    Generators[m] = generator_module
    logger.logEvent(f'module: {m}')
  except Exception as e:
    logger.logEvent(str(e))

print(Generators)

client = cclient.client

# can use global dependencies to apply auth to every endpoint
# or see individual path dependencies with /headertest2 endpoint
#app = FastAPI(dependencies=[Depends(auth_check)])

ALLOWLIST_ROUTEPREFIXES = [
   "ssoconfig",
   "login",
   "debug"
]

def returnStatus(statuscode):
    lookup = {
        "400": status.HTTP_400_BAD_REQUEST,
        "401": status.HTTP_401_UNAUTHORIZED,
        "403": status.HTTP_403_FORBIDDEN,
        "404": status.HTTP_404_NOT_FOUND
    }
    response = Response()
    response.status_code = lookup[statuscode]
    return response

"""
you can use request.state.your_custom_param  to pass data on to the route handlers from the middleware
https://stackoverflow.com/questions/64602770/how-can-i-set-attribute-to-request-object-in-fastapi-from-middleware
"""
@app.middleware("http")
async def check_auth(request: Request, call_next):
    p = request.url.path
    prefix = p.split("/")[1]
    if prefix not in ALLOWLIST_ROUTEPREFIXES:
        auth_hdr = request.headers.get('Authorization')
        '''remove the leading "Bearer" string'''
        if auth_hdr:
            parts = auth_hdr.split(' ')
            auth_hdr = parts[1] if len(parts) > 1 else None
        else:
            auth_hdr = request.cookies.get('Authorization')
        if not auth_hdr:
            return returnStatus("400")

        try:
            usrdata = authhelpers.get_usrdata_if_loggedin(auth_hdr)
            request.state.usrdata = usrdata
        except Exception as e:
            return returnStatus("401")

    response = await call_next(request)
    return response

@app.get("/tmpauthcookie")
def get_tmpauth(request: Request):
    user_uid = request.state.usrdata.get('uid')
    response = Response()
    response.set_cookie(
        "Authorization", 
        authhelpers.create_jwt("tmpauth", user_uid), 
        max_age=60, 
        path="/", 
        secure=True, 
        httponly=True, 
        samesite="strict")
    return response



# curl -kv -X POST  -F 'file=@test.js' -F 'metadata={"a":"123"}' https://10.3.3.83/webservice/import/example
@app.post("/import/{importer_name}")
async def run_import(importer_name: str, file: UploadFile, request: Request, metadata: str = Form()):
    if importer_name not in Importers:
        raise HTTPException(status_code=404, detail=f"unknown importer {importer_name}")
    '''
    - parse metadata
    - importer = Importers[importer_name]
    - importer.do_import(file, metadata)
    '''
    metadata_json = json.loads(metadata)
    importer = Importers[importer_name]
    import_result = await importer.do_import(file, metadata_json)
    return {"importer_name": importer_name, "filename": file.filename, "metadata": metadata_json, "result": import_result}


@app.post("/generate/{generator_name}")
async def run_generate(generator_name: str, request: Request):
    if generator_name not in Generators:
        raise HTTPException(status_code=404, detail=f"unknown generator {generator_name}")
    '''
    - parse metadata
    - importer = Importers[importer_name]
    - importer.do_import(file, metadata)
    '''
    metadata_dict = await request.json()
    generator = Generators[generator_name]
    generator_result = await generator.generate(metadata_dict)
    return {"result": generator_result}


@app.get("/ssoconfig")
async def get_ssoconfig():
    return {"sso": appconfig.getValue('sso')}

@app.post("/login/sso/{sso_type}")
async def post_loginsso(sso_type: str, request: Request):
    auth_token = None
    if sso_type == 'oidc_aws':
        auth_token = authhelpers.login_oidc_aws(request)
    return {"token": auth_token}

@app.get("/debug/req_headers")
async def do_debug(request: Request):
    if not appconfig.getValue('debug'):
        return {}
    return {"requestdata":request.headers}

@app.post("/login/default")
async def post_logindefault(request: Request):
    logindata = await request.json()
    auth_token = authhelpers.login_default(logindata)
    return {"token": auth_token}

@app.post("/nodes")
async def api_nodespost(request: Request):
    nodesdata = await request.json()
    return client.fetchNodesPostObj(nodesdata)

@app.post("/move")
async def api_movepost(request: Request):
    nodesdata = await request.json()
    return client.moveNodesPostObj(nodesdata)

@app.post("/upsert")
async def api_upsertpost(request: Request):
    nodesdata = await request.json()
    return client.upsertNodesPostObj(nodesdata)

@app.post("/upload")
def api_uploadfile(filedata: UploadFile, _p: str = Form()): #_p: Annotated[str, Form()],):
    form = cclient.MultiPartForm()
    form.add_field('type', 'file_upload')
    form.add_field('_p', _p)
    form.add_file('filedata', filedata.filename, fileHandle=filedata.file) #open(filedata, "rb"))
    return client.createFileNode(form)


@app.get("/download/{node_uid}")
def download_file(node_uid: str, request: Request):
    def iterfile(f):
        with open(f, mode="rb") as file_like:
            yield from file_like

    tmpfile,contenttype,disposition = client.downloadFile(node_uid)
    resp = StreamingResponse(iterfile(tmpfile), media_type=contenttype)
    resp.headers['Content-Disposition'] = disposition
    return resp


@app.get("/attachment/{attachment_uid}/{timestamp}")
async def get_attachment(attachment_uid: str, timestamp: str, request: Request):
    return client.fetchNodes(
        uid = attachment_uid, 
        field = cnode.PROP_LASTMOD, 
        op = 'gt', 
        val = timestamp, 
        depth = 0, 
        body = True)

@app.get("/test/checklogin")
async def do_testchecklogin():

    return {"check":"ok"}


'''
await request.json()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/foobar")
async def foobar():
    return {"message": "Hello Foobar"}

@app.get("/number/{id}")
async def foobar(id: int):
    return {"message": f"Hello int {id}"}


# The query is the set of key-value pairs that go after the ? in a URL, separated by & characters.
# For example, in the URL:
# http://127.0.0.1:8000/items/?skip=0&limit=10

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]
@app.get("/items/")
async def read_item(skip: int = 0, limit: int = 2, msg: str = 'nil'):
    print(f"msg: {msg}")
    return fake_items_db[skip : skip + limit]

# curl -kv -H 'x-value: laefjejflfk' https://10.3.3.83/webservice/headertest
@app.get("/headertest")
async def headertest(x_value: str = Header(default='x')):
    return {"message": f"x_value: {x_value}"}


@app.get("/headertest2", dependencies=[Depends(auth_check)])
async def headertest2():
    return {"message": "OK"}

# curl -kv -X POST  -F 'file=@test.js' -F 'metadata={"a":"123"}' https://10.3.3.83/webservice/uploadfile/xuhdh
@app.post("/uploadfile/{testparam}")
async def create_upload_file(testparam: str, file: UploadFile, metadata: str = Form()):
    return {"testparam": testparam, "filename": file.filename, "metadata": json.loads(metadata)}
'''
