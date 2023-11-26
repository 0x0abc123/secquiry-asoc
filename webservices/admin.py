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


ANONYMOUS_ROUTE_PREFIXES = [
   "ssoconfig",
   "login",
   "debug"
]

def checkIfAdmin(request, usrdata):
    return usrdata.get(authhelpers.ADMIN_FIELD)

authMiddleware = authhelpers.AuthMiddleware(anonymousRoutePrefixes=ANONYMOUS_ROUTE_PREFIXES, otherConditions=checkIfAdmin)

@app.middleware("http")
async def check_auth(request: Request, call_next):
    response = authMiddleware.getAuthorisation(request)
    if response:
        return response
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
    metadata_json = json.loads(metadata)
    importer = Importers[importer_name]
    import_result = await importer.do_import(file, metadata_json)
    return {"importer_name": importer_name, "filename": file.filename, "metadata": metadata_json, "result": import_result}


@app.post("/generate/{generator_name}")
async def run_generate(generator_name: str, request: Request):
    if generator_name not in Generators:
        raise HTTPException(status_code=404, detail=f"unknown generator {generator_name}")
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

@app.post("/query")
async def api_querypost(request: Request):
    querydata = await request.json()
    return client.queryPostObj(querydata)

@app.post("/move")
async def api_movepost(request: Request):
    nodesdata = await request.json()
    return client.moveNodesPostObj(nodesdata)

@app.post("/link")
async def api_linkpost(request: Request):
    nodesdata = await request.json()
    return client.linkNodesPostObj(nodesdata)

@app.post("/unlink")
async def api_unlinkpost(request: Request):
    nodesdata = await request.json()
    return client.unlinkNodesPostObj(nodesdata)

@app.post("/upsert")
async def api_upsertpost(request: Request):
    nodesdata = await request.json()
    return client.upsertNodesPostObj(nodesdata)

@app.post("/upload")
def api_uploadfile(filedata: UploadFile, p: str = Form()):
    form = cclient.MultiPartForm()
    form.add_field('type', 'file_upload')
    form.add_field('_p', p)
    form.add_file('filedata', filedata.filename, fileHandle=filedata.file)
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


