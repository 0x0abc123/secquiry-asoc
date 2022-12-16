# uvicorn main:app --port 8800

from fastapi import FastAPI, Header, Depends, HTTPException, UploadFile, Form, Request
import json

def auth_check(request: Request, issue: str = 'nil', app: str = 'nil', x_value: str = Header(default='x')):
    print('auth_check: '+x_value)
    print(request.url.path)
    print(f'authcheck app:{app}')
    print(f'authcheck issue:{issue}')
    if x_value == 'x':
        raise HTTPException(status_code=401, detail="unauthorized")
    return x_value

# can use global dependencies to apply auth to every endpoint
# or see individual path dependencies with /headertest2 endpoint
#app = FastAPI(dependencies=[Depends(auth_check)])
app = FastAPI()


# curl -kv -X POST  -F 'file=@test.js' -F 'metadata={"a":"123"}' https://10.3.3.83/webservice/import/example
@app.post("/test/{app}", dependencies=[Depends(auth_check)])
async def dostuff1(app: str, request: Request):
    print('test app')
    return {}

@app.get("/test/{app}/{issue}", dependencies=[Depends(auth_check)])
async def dostuff1(app: str, issue: str, request: Request):
    print('test app issue')
    return {}


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
