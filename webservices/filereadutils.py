# uploadfile read utils

# !!! change parser to https://pypi.org/project/defusedxml/ to prevent DoS
import xml.etree.ElementTree as ETree
import json
#import ast
import yaml

# returns text content of file as a single string
async def getTextFromFileUpload(fileupload):
    contents = ''
    await fileupload.seek(0)
    while True:
        line = await fileupload.read(1024)
        if not line:
            break
        contents += line.decode('utf-8')
    return contents

# returns list of lines of text
async def getLinesOfTextFromFileUpload(fileupload):
    contents = await getTextFromFileUpload(fileupload)
    return contents.split('\n')

# returns XML root element (xml.etree.Element)
async def getXMLTreeFromFileUpload(fileupload):
    xmlText = await getTextFromFileUpload(fileupload)
    #etree = ETree.fromstring(xmlText)
    #return etree.getroot()
    return ETree.fromstring(xmlText)

async def getJsonObjFromFileUpload(fileupload):
    jsonSerialized = await getTextFromFileUpload(fileupload)
    # strip newlines and control chars
    s = jsonSerialized.replace('\r','').replace('\n','')
    #return ast.literal_eval(s) #json.loads(s)
    #tree = ast.parse(s)
    #print(ast.dump(tree))
    retval = None
    try:
        retval = json.loads(s)
    except Exception as e:
        # may have failed due to JSON5 formatting eg. trailing commas
        # so try with YAML parser
        retval = yaml.safe_load(s)
    return retval