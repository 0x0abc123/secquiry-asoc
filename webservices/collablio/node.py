import uuid

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
PROP_LINKLIST = "lnk"
PROP_INLINKLIST = "inl"

TYPE_CLIENT = "Client"
TYPE_PROJECT = "Project"
TYPE_FOLDER = "Folder"
TYPE_HOST = "Host"
TYPE_PORT = "Port"
TYPE_TEXT = "Text"
TYPE_IMAGE = "Image"
TYPE_FILE = "File"
TYPE_NOTE = "Note"
TYPE_CODE = "Code"
TYPE_TABLE = "Table"
TYPE_ANNOTATION = "Annotation"
TYPE_TAG = "Tag"
TYPE_REPORT = "Report"
TYPE_SECTION = "Section"
TYPE_FINDINGS = "Findings"
TYPE_JSON = "Json"
TYPE_MARKDOWN = "Markdown"
TYPE_TASK = "Task"
TYPE_CREDENTIALS = "Credentials"
TYPE_USER = "User"

class Node:
    
    def __init__(self, _type):
        self.Type = _type
        self.Children = []
        self.ParentUids = []  # list of UIDs, whereas self.Children is a list of Node instances
        self.UID = str(uuid.uuid4())
        self.Label = ''
        self.Detail = ''
        self.CustomData = ''
        self.TextData = ''
        self.OutLinks = []
        self.InLinkUids = []  # list of UIDs, whereas self.OutLinks is a list of Node instances

    def populateFromDict(self, apiFormatNode):

        self.Type = apiFormatNode[PROP_TYPE]
        #if PROP_CHILDLIST in apiFormatNode:
        #    self.Children = [n[PROP_UID] for n in apiFormatNode[PROP_CHILDLIST]]
        if PROP_PARENTLIST in apiFormatNode:
            self.ParentUids = [n[PROP_UID] for n in apiFormatNode[PROP_PARENTLIST]]
        if PROP_INLINKLIST in apiFormatNode:
            self.InLinkUids = [n[PROP_UID] for n in apiFormatNode[PROP_INLINKLIST]]
        self.UID = apiFormatNode[PROP_UID]
        self.Label = apiFormatNode[PROP_LABEL]
        self.Detail = apiFormatNode[PROP_DETAIL]
        self.CustomData = apiFormatNode[PROP_CUSTOM]
        self.TextData = apiFormatNode[PROP_TEXTDATA] if PROP_TEXTDATA in apiFormatNode else ''
    
    def convert(self):
        apiFormatNode = {}
        apiFormatNode[PROP_UID] = self.UID
        apiFormatNode[PROP_TYPE] = self.Type
        apiFormatNode[PROP_LABEL] = self.Label
        apiFormatNode[PROP_DETAIL] = self.Detail
        apiFormatNode[PROP_TEXTDATA] = self.TextData
        apiFormatNode[PROP_CUSTOM] = self.CustomData
        #only need to specify the parent UID for the node if it doesn't have a UID yet (i.e. creating a new node)
        apiFormatNode[PROP_PARENTLIST] = [{PROP_UID : self.ParentUids[0]}] if (len(self.ParentUids) > 0) else []
        apiFormatNode[PROP_CHILDLIST] = [{PROP_UID : child.UID} for child in self.Children]
        #only need to specify the inlink UID for the node if it doesn't have a UID yet (i.e. creating a new node)
        apiFormatNode[PROP_INLINKLIST] = [{PROP_UID : link} for link in self.InLinkUids]
        apiFormatNode[PROP_CHILDLIST] = [{PROP_UID : link.UID} for link in self.OutLinks]
        return apiFormatNode
        
def recursiveConvertNodesToAPIFormat(node, listToAddTheNodeTo):
    listToAddTheNodeTo.append(node.convert())
    for child in node.Children:
        recursiveConvertNodesToAPIFormat(child, listToAddTheNodeTo)

