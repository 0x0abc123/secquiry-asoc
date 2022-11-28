// show an image in full-screen view
function toggleImgFullscreen() {
  let elem = document.getElementById("imgview");

  if (!document.fullscreenElement) {
    elem.requestFullscreen().catch(err => {
      alert(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
    });
  } else {
    document.exitFullscreen();
  }
}

// open a new window/tab to display an attachment/image
function openNewWindow(url, dataURI = null) {
  var win = window.open(url, '_blank');
  if(dataURI) {
	if(dataURI.startsWith("data:image")) {
		var img = new Image();
		img.src = dataURI;
		win.document.write(img.outerHTML);
	}		
  }
  win.focus();
}

// basic notification display (TODO: make it look nicer)
function notification(msg) {
	alert(msg);
}

// when the user is editing content and they navigate away from the page, warn of unsaved changes being lost
warnOnNavigateAway = false;

// constants for node property names
const TYPE_ROOT = "__ROOT__";
const PROP_UID = "uid";
const PROP_TYPE = "ty";
const PROP_LABEL = "l";
const PROP_DETAIL = "d";
const PROP_TEXTDATA = "x";
const PROP_CUSTOM = "c";
const PROP_TIME = "t";
const PROP_LASTMOD = "m";
const PROP_BINARYDATA = "b";
const PROP_EDITING = "e";
const PROP_PARENTLIST = "in";
const PROP_CHILDLIST = "out";
const PROP_RELATIONS = "lnk";
const PROP_PARENTREFS = "inrefs";
const PROP_CHILDREFS = "outrefs";
const PROP_VUEREF = 'vueref'; // pointer to a vue object if there is one linked to the node

// create a new empty node
function emptyNode(_uid = '', type = '') { 

	let node = {};
	node[PROP_UID] = _uid;
	node[PROP_TYPE] = type;
	node[PROP_LABEL] = '';
	node[PROP_DETAIL] = '';
	node[PROP_TEXTDATA] = '';
	node[PROP_CUSTOM] = '';
	node[PROP_TIME] = '';
	node[PROP_LASTMOD] = '';
	node[PROP_BINARYDATA] = '';
	node[PROP_EDITING] = '';
	node[PROP_PARENTLIST] = [];
	node[PROP_CHILDLIST] = [];
	node[PROP_PARENTREFS] = [];
	node[PROP_CHILDREFS] = [];
	node[PROP_RELATIONS] = [];
	node.hasChanged = false; // flag if modified
	node.isViewed = false;  // UI highlights if something hasn't been viewed yet (eg. with bold font)
	node.isOpen = false; // for tree-view, show [+] or [-] depending on whether children are expanded
	node.showChildren = true; // for tree-view, allow children to be expanded
	return node;
};

// create the root data structures
// the root uid '.' should get translated to the actual root node UID by the backend
// the index is a dict that maps node UIDs to node objects
// G is our global namespace (need to tidy up the codebase to use it everywhere, as there are some global)
var _root = emptyNode('.',TYPE_ROOT);
var _index = {};
var G = { root : _root , ctxmenuData: emptyCtxMenuData()};

_index[_root.uid] = _root;
_root.l = "All Categories";

// The UI design is based around Panes and pane-subtypes
// currently there are 2 basic pane types: main (shows in the right-side pane) and modal
// _defaultPaneConfigs is a repository of configuration data for the various default views that will be shown in the main pane or modal dialogs of the UI.
// Each node type can use a non-default pane type for view, edit or add actions 
//	(a node type should specify the pane types it uses in _typeConfigs)
//	(configuration for pane types is found in the _panesIndex)
//  (the actual pane needs to be created in the HTML file)
//  (an associated VueJS component/binding needs to be created below)
// Within each pane configuration dictionary, the key/value pairs consist of:
// key->"<subtype>" : value->a function that returns a config object
// a config object can contain whatever key/value pairs the pane-type understands
// for the default panes, the returned config object's keys correspond to node properties, 
//   and define whether those properties will be visible or editable, and their label in the UI
// the view can ignore the config properties though

var _defaultPaneConfigs = {

	// configs for the main pane:
	view: {
		"default" : function() {
			return {
				label: { visible: true, name: "Label" },
				detail: { visible: true, name: "Detail" },
				custom: { visible: true, name: "Custom Data" },
				textdata: { visible: true, name: "Text Data" },
				eventtime: { visible: true, name: "Event Time" },
				title: '',
			};
		},
	},
	edit: {
		"default" : function() {
			return {
				label: { visible: true, editable: true, name: "Label", required: true },
				detail: { visible: true, editable: true, name: "Detail", required: true },
				custom: { visible: true, editable: true, name: "Custom Data", required: false },
				textdata: { visible: true, editable: true, name: "Text Data", required: false },
				eventtime: { visible: true, editable: true, name: "Event Time", required: false },
				title: '',
			};
		},
	},
	othermain: {
		"search" : function() {
			return {
				title: '',
				results: { 
					nodes: [emptyNode('0x0',TYPE_ROOT)],
					nodelabel: '<blank>',
					query: '<blank>',
				}
			};
		},
	},
	// configs for modal dialog:
	add: {
		"default" : function() {
			return {
				label: { visible: true, editable: true, name: "Label", required: true },
				detail: { visible: true, editable: true, name: "Detail", required: true },
				custom: { visible: true, editable: true, name: "Custom Data", required: false },
				textdata: { visible: true, editable: true, name: "Text Data", required: false },
				eventtime: { visible: true, editable: true, name: "Event Time", required: false },
				title: '',
			};
		},
	},
	// TODO: implement these
	// most of the moving nodes around is done via drag and drop, but these might be useful for moving large volumes of sibling nodes
	moveparent:  {
		"default" : function() { return {} },
	},
	movechildren: {
		"default" : function() { return {} },
	}
};

// load the config data for a pane and subtype from the _defaultPaneConfigs repository
// we create a separate node object in the config so it can be modified by the view without changing the copy in the master index
// for example if editing is cancelled by the user
function getDefaultConfig(panetype, subtype = 'default')
{
	let conf = _defaultPaneConfigs[panetype][subtype]();
	if(!conf) conf = {};
	conf.nodeinfo = emptyNode();
	return conf;
}

// _typeConfigs is a repository of config data for the different node types (Client, Project, Note, Image etc)
// eg. what types of nodes can be children of a given type, what view/subtype to use to display or edit it
var _typeConfigs = {};

// config for the "root" node type
let rootConfig = 
 {
		typesAllowedForChildNodes : new Set(),
		actionViewConf: { paneType: "default", config: getDefaultConfig('view') },
		actionAddConf: { paneType: "default", config: getDefaultConfig('add') },
		actionEditConf: { paneType: "default", config: getDefaultConfig('edit') },
		iconClassName: 'ico-folder',
		showChildren: true
}
_typeConfigs[TYPE_ROOT] = rootConfig;

// factory method to create base object for all node types
// will automatically add the type config object to the _typeConfigs repository
function createTypeConfigWithDefaults(
	typename,
	listOfAllowedChildren = [], 
	iconClass = '',
	canAddToTopLevel = true,
	view = 'default', 
	add = 'default', 
	edit = 'default', 
	moveparent = 'default', 
	movechildren = 'default') {

	let newTC = {};
	newTC.typesAllowedForChildNodes = new Set(listOfAllowedChildren);
	newTC.actionViewConf = (view) ? { paneType: view, config: getDefaultConfig('view') } : null;
	newTC.actionAddConf = (add) ? { paneType: add, config: getDefaultConfig('add') } : null;
	newTC.actionEditConf = (edit) ? { paneType: edit, config: getDefaultConfig('edit') } : null;
	newTC.actionMoveParentConf = (moveparent) ? { paneType: "default", config: {} } : null;
	newTC.actionMoveChildrenConf = (movechildren) ? { paneType: "default", config: {} } : null;
	newTC.iconClassName = iconClass || 'ico-miscfile';
	newTC.getValueForSorting = ((node) => {	return node[PROP_LABEL]; })
	newTC.showChildren = true;
	
	if(canAddToTopLevel) 
		rootConfig.typesAllowedForChildNodes.add(typename);
	_typeConfigs[typename] = newTC;
	return newTC;

}
// create a default type for when we receive an unknown node type from the backend
createTypeConfigWithDefaults('unknown',[],'',false);

// when adding a new type to the app, we have to configure it below, plus add it to ctxmenu and 
/*
TYPE_FOOBAR = "foobar";
createTypeConfigWithDefaults(TYPE_FOOBAR, [TYPE_BLAH,...]
// alternatively, longhand...
_typeConfigs[TYPE_FOOBAR] = {
		typesAllowedForChildNodes : new Set([TYPE_BLAH,...]),
		actionViewConf: { paneType: "default", config: {...} },
		...
		getValueForSorting: function(node) {...}
	}
_typeConfigs[TYPE_ROOT].typesAllowedForChildNodes.add("foobar");

*/
const TYPE_CLIENT = "Client";
const TYPE_PROJECT = "Project";
const TYPE_FOLDER = "Folder";
const TYPE_HOST = "Host";
const TYPE_PORT = "Port";
const TYPE_TEXT = "Text";
const TYPE_IMAGE = "Image";
const TYPE_FILE = "File";
const TYPE_NOTE = "Note";
const TYPE_CODE = "Code";
const TYPE_TABLE = "Table";
const TYPE_ANNOTATION = "Annotation";
const TYPE_TAG = "Tag";
const TYPE_REPORT = "Report";
const TYPE_SECTION = "Section";
const TYPE_JOBREQ = "Job Request";
const TYPE_TASK = "Task";
const TYPE_AGENT = "Agent";
const TYPE_SERVICE = "Service";
const TYPE_JSON = "Json";
const TYPE_MARKDOWN = "Markdown";
const TYPE_FINDINGS = "Findings";

createTypeConfigWithDefaults(TYPE_CLIENT, [TYPE_FOLDER, TYPE_PROJECT, TYPE_NOTE, TYPE_TABLE, TYPE_ANNOTATION, TYPE_FILE],'ico-user');

let c_project = createTypeConfigWithDefaults(TYPE_PROJECT, [TYPE_FOLDER, TYPE_REPORT, TYPE_NOTE, TYPE_TABLE, TYPE_TEXT, TYPE_IMAGE, TYPE_ANNOTATION, TYPE_FILE],'ico-book',false);
c_project.actionViewConf.config.showImportButton = true;

let c_folder = createTypeConfigWithDefaults(TYPE_FOLDER, [TYPE_FOLDER, TYPE_CLIENT, TYPE_PROJECT, TYPE_NOTE, TYPE_TABLE, TYPE_TEXT, TYPE_ANNOTATION, TYPE_FILE, TYPE_IMAGE, TYPE_TAG, TYPE_HOST, TYPE_PORT, TYPE_REPORT, TYPE_SECTION, TYPE_CODE, TYPE_TASK, TYPE_AGENT, TYPE_SERVICE, TYPE_JSON, TYPE_MARKDOWN, TYPE_FINDINGS ],'ico-folder');
c_folder.actionViewConf.config.showImportButton = true;

let c_host = createTypeConfigWithDefaults(TYPE_HOST, [TYPE_FOLDER, TYPE_PORT, TYPE_IMAGE, TYPE_TEXT, TYPE_NOTE, TYPE_TABLE, TYPE_ANNOTATION, TYPE_FILE],'ico-host',false);
c_host.getValueForSorting = (node) => {	return convertIPtoNum(node[PROP_LABEL]); }

let c_port = createTypeConfigWithDefaults(TYPE_PORT, [TYPE_FOLDER, TYPE_PROJECT, TYPE_NOTE, TYPE_TABLE, TYPE_TEXT, TYPE_ANNOTATION, TYPE_FILE, TYPE_IMAGE],'ico-hash',false);
c_port.getValueForSorting = (node) => {	return parseInt(node[PROP_LABEL].replace('/tcp','').replace('/udp',''),10); }

let c_img = createTypeConfigWithDefaults(TYPE_IMAGE, [TYPE_ANNOTATION],'ico-img',false,'download','fileupload',null);
c_img.signedurl = '';

createTypeConfigWithDefaults(TYPE_TEXT, [TYPE_ANNOTATION],'ico-code',false,'textbody',null,null);
createTypeConfigWithDefaults(TYPE_FILE, [TYPE_ANNOTATION],'ico-miscfile',false,'download','fileupload',null);
createTypeConfigWithDefaults(TYPE_NOTE, [TYPE_ANNOTATION],'ico-note',false,'editor','editor','editor');
createTypeConfigWithDefaults(TYPE_TABLE, [TYPE_ANNOTATION],'ico-table',false,'table','table','table');
createTypeConfigWithDefaults(TYPE_ANNOTATION, [],'ico-info',false,null,null,'default');
createTypeConfigWithDefaults(TYPE_TAG, [TYPE_FOLDER, TYPE_CLIENT, TYPE_PROJECT, TYPE_NOTE, TYPE_TABLE, TYPE_TEXT, TYPE_ANNOTATION, TYPE_FILE, TYPE_IMAGE, TYPE_TAG, TYPE_HOST, TYPE_PORT, TYPE_REPORT],'ico-tag',false);
let c_report = createTypeConfigWithDefaults(TYPE_REPORT, [TYPE_SECTION, TYPE_JOBREQ],'ico-report',false);
c_report.actionViewConf.config.generators = [{'id':'report','btnLabel':'Generate Report'}];

createTypeConfigWithDefaults(TYPE_SECTION, [TYPE_SECTION, TYPE_NOTE, TYPE_TABLE, TYPE_ANNOTATION, TYPE_FILE, TYPE_TEXT, TYPE_IMAGE],'ico-mark',false);
createTypeConfigWithDefaults(TYPE_JOBREQ, [],'ico-send',false,'default','default','default');
createTypeConfigWithDefaults(TYPE_CODE, [TYPE_ANNOTATION],'ico-miscfile',false,'codeedit',null,'codeedit');
createTypeConfigWithDefaults(TYPE_TASK, [],'ico-send',false,'textbody','task','task');
createTypeConfigWithDefaults(TYPE_AGENT, [],'ico-send',false,'default','default','testtaskagent');
createTypeConfigWithDefaults(TYPE_SERVICE, [],'ico-send',false,'default','default','default');
createTypeConfigWithDefaults(TYPE_JSON, [TYPE_ANNOTATION],'ico-miscfile',false,'json',null,null);
createTypeConfigWithDefaults(TYPE_MARKDOWN, [TYPE_ANNOTATION],'ico-miscfile',false,'textbody',null,null);
let c_findings = createTypeConfigWithDefaults(TYPE_FINDINGS, [TYPE_ANNOTATION],'ico-miscfile',false,'findings',null,null);
c_findings.showChildren = false;

// About config.nodeinfo
// we don't bind the collablio node data directly to a Vue component (eg. the node type's add, edit, view UIs)
// this is so that we dont affect the original node data if the user decides to cancel any changes for an "edit" action
// and it is also populated with empty collablio node data in the case of an "add" action
// we copy the original collablio node data into the config.nodeinfo and bind that to the Vue component

// write a loop that iterates thru all typeConfigs and checks whether its members contain config.nodeinfo
// if not, create an empty node.... or maybe just force set it???

function setNodeInfo(typeConfObj, actionConf)
{
	if(typeConfObj[actionConf] && typeConfObj[actionConf].config && !typeConfObj[actionConf].config.nodeinfo) 
		typeConfObj[actionConf].config.nodeinfo = emptyNode();
}

for (const [key, value] of Object.entries(_typeConfigs)) {
	//console.log(`${key}: ${value}`);
	setNodeInfo(value, 'actionViewConf');
	setNodeInfo(value, 'actionEditConf');
	setNodeInfo(value, 'actionAddConf');
	setNodeInfo(value, 'actionMoveParentConf');
	setNodeInfo(value, 'actionMoveChildrenConf');
}

///****************** Move Vue bindings here, and the panesIndex will be bound to the vue components' data.v objects 
// eg. v_editAndView_editor.$data.v
// eg. v_editAndView_editor.$root.testEventHandler

// _panesIndex is a repository of config data for each different UI view or dialog type and their subtypes
// The HTML needs to contain a div with an ID that corresponds to the one provided in the config
// A VueJS component and binding also needs to be created
// the config data contains:
// divID -> the HTML DOM element ID that the view will be rendered inside of
// v -> an object that the vueJS component will bind to (changing the values in the object and its children should dynamically update the UI)
// onBeforeShow -> hook function called before the view is made visible (fetch data or prepare node property values in here)
// onAfterSubmit -> hook function called after the user clicks the submit/save button when view allows editing 
// in the hook functions, get config data using this.v.config  (this contains node info and its parent node UID)
var _panesIndex = {

	view: {
		"default" : {
			divID: "view_default",
			v: { config: getDefaultConfig('view')},
			onBeforeShow: function(){},
		},
		"findings" : {
			divID: "view_findings",
			v: { config: getDefaultConfig('view')},
			onBeforeShow: function(){fetchChildNodes(this.v.config.nodeinfo[PROP_UID])},
		},
		"download" : {
			divID: "view_download",
			v: { config:  getDefaultConfig('view')},
			onBeforeShow: async function(){ 
				let nodeInfo = this.v.config.nodeinfo;
				if (nodeInfo[PROP_TYPE] == TYPE_IMAGE) {
					await updateAttachmentNodeIfChangedOrEmpty(nodeInfo, PROP_BINARYDATA);
					v_view_download.$forceUpdate(); 
				}
			},
		},
		"textbody" : {
			divID: "view_textbody",
			v: { config:  getDefaultConfig('view')},
			onBeforeShow: async function(){
				let nodeInfo = this.v.config.nodeinfo;
				await updateAttachmentNodeIfChangedOrEmpty(nodeInfo);
				//without the forceUpdate, the TextData is not showing upon the first viewing attempt, but will show on the second
				v_view_textbody.$forceUpdate(); 
			}, 
		},
		"editor" : {
			divID: "view_editor",
			v: { config:  getDefaultConfig('view')},
			onBeforeShow: async function(){
				//need to fetch attachment body and populate quill
				let nodeInfo = this.v.config.nodeinfo;
				await updateAttachmentNodeIfChangedOrEmpty(nodeInfo);
				populateQuill(nodeInfo);
				setQuillVisualState("disable");
				warnOnNavigateAway = false;
				quillGlobal.CurrentUid = nodeInfo[PROP_UID];
			},
		},
		"codeedit" : {
			divID: "view_codeedit",
			v: { config:  getDefaultConfig('view')},
			onBeforeShow: async function(){
				//need to fetch attachment body and populate quill
				let nodeInfo = this.v.config.nodeinfo;
				await updateAttachmentNodeIfChangedOrEmpty(nodeInfo);
				await populateCodeEdit(nodeInfo);
				setCodeEditVisualState("disable");
				warnOnNavigateAway = false;
				codeEditGlobal.CurrentUid = nodeInfo[PROP_UID];
			},
		},
		"json" : {
			divID: "view_json",
			v: { config:  getDefaultConfig('view')},
			onBeforeShow: async function(){
				//need to fetch attachment body and populate viewer
				let nodeInfo = this.v.config.nodeinfo;
				await updateAttachmentNodeIfChangedOrEmpty(nodeInfo);
				//console.log('json.onBeforeShow:',nodeInfo[PROP_TEXTDATA]);
				setJSON(JSON.parse(nodeInfo[PROP_TEXTDATA]));
			},
		},
		"table" : {
			divID: "view_table",
			v: { config:  getDefaultConfig('view')},
			onBeforeShow: async function(){
				let nodeInfo = this.v.config.nodeinfo;
				await updateAttachmentNodeIfChangedOrEmpty(nodeInfo);
				populateJexcel(nodeInfo);
				setJexcelVisualState("disable");
				warnOnNavigateAway = false;
				jexcelGlobal.CurrentUid = nodeInfo[PROP_UID];
			},
		},

	},
	othermain: {
		"search" : {
			divID: "othermain_search",
			v: { config: _defaultPaneConfigs['othermain']['search']()},
			onBeforeShow: function(){},
		},
	},
	// for "edit" panetypes:
	// onBeforeCopyNode() this.v.config.nodeinfo contains the *original* node, to allow actions on it to occur
	// onBeforeShow()  this.v.config.nodeinfo contains a copy of the node, run before the pane is shown
	// onAfterSubmit() this.v.config.nodeinfo contains a copy of the node, run after submitAction button is clicked (send API upsert requests in here)
	edit: {
		"default" : {
			divID: "edit_default",
			v: { config:  getDefaultConfig('edit')},
			onBeforeShow: function(){},
			onAfterSubmit: async function(){ await upsertGeneric(this.v.config.nodeinfo); warnOnNavigateAway = false; },
		},
		"editor" : {
			divID: "view_editor",
			v: { config:  getDefaultConfig('edit')},
			onBeforeCopyNode: async function(){
				//need to fetch attachment body if its not there or it needs an update
				await updateAttachmentNodeIfChangedOrEmpty(this.v.config.nodeinfo);
			},
			onBeforeShow: function(){
				populateQuill(this.v.config.nodeinfo);
				setQuillVisualState("enable");
				warnOnNavigateAway = true;
			},
			onAfterSubmit: async function(){
				let nodeInf = this.v.config.nodeinfo;
				getQuillEdits(nodeInf);
				let x_changed = (nodeInf[PROP_TEXTDATA] != _index[nodeInf[PROP_UID]][PROP_TEXTDATA]);
				let l_changed = (nodeInf[PROP_LABEL] != _index[nodeInf[PROP_UID]][PROP_LABEL]);
				if(!x_changed)
					nodeInf[PROP_TEXTDATA] = null;
				if(x_changed || l_changed)
					await upsertGeneric(nodeInf);
				setQuillVisualState("disable");
				warnOnNavigateAway = false;
				quillGlobal.CurrentUid = nodeInf[PROP_UID];
			},
		},
		"codeedit" : {
			divID: "view_codeedit",
			v: { config:  getDefaultConfig('edit')},
			onBeforeCopyNode: async function(){
				//need to fetch attachment body if its not there or it needs an update
				await updateAttachmentNodeIfChangedOrEmpty(this.v.config.nodeinfo);
			},
			onBeforeShow: async function(){
				await populateCodeEdit(this.v.config.nodeinfo);
				setCodeEditVisualState("enable");
				warnOnNavigateAway = true;
			},
			onAfterSubmit: async function(){
				let nodeInf = this.v.config.nodeinfo;
				getCodeEdits(nodeInf);
				let x_changed = (nodeInf[PROP_TEXTDATA] != _index[nodeInf[PROP_UID]][PROP_TEXTDATA]);
				if(!x_changed)
					nodeInf[PROP_TEXTDATA] = null;
				else
					await upsertGeneric(nodeInf);
				setCodeEditVisualState("disable");
				warnOnNavigateAway = false;
				codeEditGlobal.CurrentUid = nodeInf[PROP_UID];
			},
		},
		"testtaskagent" : {
			divID: "edit_testform",
			v: { config:  getDefaultConfig('edit')},
			onBeforeShow: async function(){
				//need to fetch attachment body and populate quill
				let nodeInfo = this.v.config.nodeinfo;
				await updateAttachmentNodeIfChangedOrEmpty(nodeInfo);
				//await populateCodeEdit(nodeInfo);
				//setCodeEditVisualState("disable");
				warnOnNavigateAway = true;
				//codeEditGlobal.CurrentUid = nodeInfo[PROP_UID];
			},
			onAfterSubmit: async function(){
				let nodeInf = this.v.config.nodeinfo;
				//getJexcelEdits(nodeInf);
				//let x_changed = (nodeInf[PROP_TEXTDATA] != _index[nodeInf[PROP_UID]][PROP_TEXTDATA]);
				//let l_changed = (nodeInf[PROP_LABEL] != _index[nodeInf[PROP_UID]][PROP_LABEL]);
				//if(!x_changed)
				//	nodeInf[PROP_TEXTDATA] = null;
				//if(x_changed || l_changed)
					await upsertGeneric(nodeInf);
				//setJexcelVisualState("disable");
				warnOnNavigateAway = false;
				//jexcelGlobal.CurrentUid = nodeInf[PROP_UID];
			},		
		},
		"table" : {
			divID: "view_table",
			v: { config:  getDefaultConfig('edit')},
			onBeforeCopyNode: async function(){
				//need to fetch attachment body if its not there or it needs an update
				await updateAttachmentNodeIfChangedOrEmpty(this.v.config.nodeinfo);
			},
			onBeforeShow: function(){
				populateJexcel(this.v.config.nodeinfo);
				setJexcelVisualState("enable");
				warnOnNavigateAway = true;
			},
			onAfterSubmit: async function(){
				let nodeInf = this.v.config.nodeinfo;
				getJexcelEdits(nodeInf);
				let x_changed = (nodeInf[PROP_TEXTDATA] != _index[nodeInf[PROP_UID]][PROP_TEXTDATA]);
				let l_changed = (nodeInf[PROP_LABEL] != _index[nodeInf[PROP_UID]][PROP_LABEL]);
				if(!x_changed)
					nodeInf[PROP_TEXTDATA] = null;
				if(x_changed || l_changed)
					await upsertGeneric(nodeInf);
				setJexcelVisualState("disable");
				warnOnNavigateAway = false;
				jexcelGlobal.CurrentUid = nodeInf[PROP_UID];
			},		
		},
		"task" : {
			divID: "edit_task",
			v: { config:  getDefaultConfig('edit')},
			onBeforeCopyNode: async function(){
				//need to fetch attachment body if its not there or it needs an update
				await updateAttachmentNodeIfChangedOrEmpty(this.v.config.nodeinfo);
			},
			onBeforeShow: function(){
				//populateJexcel(this.v.config.nodeinfo);
				//setJexcelVisualState("enable");
				warnOnNavigateAway = true;
			},
			onAfterSubmit: async function(){
				let nodeInf = this.v.config.nodeinfo;
				//getJexcelEdits(nodeInf);
				let x_changed = (nodeInf[PROP_TEXTDATA] != _index[nodeInf[PROP_UID]][PROP_TEXTDATA]);
				let l_changed = (nodeInf[PROP_LABEL] != _index[nodeInf[PROP_UID]][PROP_LABEL]);
				let c_changed = (nodeInf[PROP_CUSTOM] != _index[nodeInf[PROP_UID]][PROP_CUSTOM]);
				let d_changed = (nodeInf[PROP_DETAIL] != _index[nodeInf[PROP_UID]][PROP_DETAIL]);
				if(!x_changed)
					nodeInf[PROP_TEXTDATA] = null;
				if(x_changed || l_changed || c_changed || d_changed)
					await upsertGeneric(nodeInf);
				//setJexcelVisualState("disable");
				warnOnNavigateAway = false;
				//jexcelGlobal.CurrentUid = nodeInf[PROP_UID];
			},		
		},	},
	//modal dialog views:
	add: {
		"default" : {
			divID: "add_default",
			v: { config:  getDefaultConfig('add')},
			onBeforeShow: function(){},
			onAfterSubmit: async function(){ await upsertGeneric(this.v.config.nodeinfo); },
			},
		"fileupload" : {
			divID: "add_fileupload",
			v: { config:  getDefaultConfig('add')},
			onBeforeShow: function(){clearFileUploadFormInput();},
			onAfterSubmit: async function(){ await fileupload(this.v.config.nodeinfo);},
			},
		"importupload" : {
			divID: "import_fileupload",
			v: { config:  getDefaultConfig('add')},
			onBeforeShow: function(){clearImportUploadFormInput();},
			onAfterSubmit: async function(){ await importupload(this.v.config.importer, this.v.config.under_uid);},
			},
		"generator" : {
			divID: "add_generator",
			v: { config:  getDefaultConfig('add')},
			onBeforeShow: function(){},
			onAfterSubmit: async function(){ await generate(this.v.config.generator, this.v.config.params, this.v.config.under_uid);},
			},
		"editor" : { //we show a dialog to enter the note name, create the empty note and show the actual editor
			divID: "add_editor",
			v: { config:  getDefaultConfig('add')},
			onBeforeShow: function(){},
			onAfterSubmit: async function(){
				let ninfo = this.v.config.nodeinfo;
				await upsertGeneric(ninfo); 
				v_action_funcs['edit'](ninfo[PROP_UID]);
				},
			},
		"table" : { //we show a dialog to enter the table name, create the empty grid and show the actual editor
			divID: "add_table",
			v: { config:  getDefaultConfig('add')},
			onBeforeShow: function(){},
			onAfterSubmit: async function(){
				let ninfo = this.v.config.nodeinfo;
				await upsertGeneric(ninfo); 
				v_action_funcs['edit'](ninfo[PROP_UID]);
				},
			},
		"task" : { //we show a dialog to enter the table name, create the empty grid and show the actual editor
			divID: "add_task",
			v: { config:  getDefaultConfig('add')},
			onBeforeShow: function(){},
			onAfterSubmit: async function(){
				let ninfo = this.v.config.nodeinfo;
				await upsertGeneric(ninfo); 
				v_action_funcs['edit'](ninfo[PROP_UID]);
				},
			},
	},
	moveparent:  {
		"default" : {},
	},
	movechildren: {
		"default" : {},
	}
};

// Navigation History Stuff
// the history list contains objects containing the view type and variable data that might contain the node UID or search query etc:
// [ {'type':'viewNode','data':'0x123'}, {'type':'viewSearch', 'data': 's1'}... ]

const HISTORY_VIEWNODE = 'node';
const HISTORY_SEARCH = 'search';

var MainPaneHistory = [];
var HistoryPosition = -1;

function isOKToNavigateAway() {
	if (warnOnNavigateAway) {
		let discardChanges = confirm("Leave Page? Clicking OK will discard any edits you have made. If you have unsaved changes, click Cancel and save your changes.");
		if (discardChanges) {
			warnOnNavigateAway = false;
		}
		else 
			return false;
	}
	return true;
}

function historyPush(type, data) {
	if(!isOKToNavigateAway())
		return false;
	if (HistoryPosition > -1)
		MainPaneHistory = MainPaneHistory.slice(0,HistoryPosition+1);
	MainPaneHistory.push({'type':type, 'data': data});
	HistoryPosition++;
	setNavIcons();
	return true;
}

function setNavIcons() {
	vue_topnav.$data.iconBack = (HistoryPosition > 0) ? 'ico-left-arr' : 'ico-left-arr-dis'
	vue_topnav.$data.iconFwd = (HistoryPosition < MainPaneHistory.length - 1) ? 'ico-right-arr' : 'ico-right-arr-dis'
}

function historyBack() {
	if (HistoryPosition > 0) {
		HistoryPosition--;
	}
	setNavIcons();
	return MainPaneHistory[HistoryPosition];
}

function historyForward() {
	if(HistoryPosition < MainPaneHistory.length - 1) {
		HistoryPosition++;
	}
	setNavIcons();
	return MainPaneHistory[HistoryPosition];
}

function navigateMainPaneBack() {

	if(!isOKToNavigateAway())
		return false;

	let prevView = historyBack();
	if (!prevView)
		return;
	let prevAction = prevView['type'] == HISTORY_VIEWNODE ? 'view' : 'search';
	v_action_funcs[prevAction](prevView['data']);
}

function navigateMainPaneForward() {

	if(!isOKToNavigateAway())
		return false;
	let nextView = historyForward();
	if (!nextView)
		return;
	let nextAction = nextView['type'] == HISTORY_VIEWNODE ? 'view' : 'search';
	v_action_funcs[nextAction](nextView['data']);
}

function hasNextHistory() {
	return (HistoryPosition < MainPaneHistory.length - 2)
}

function hasPrevHistory() {
	return (HistoryPosition > 0)
}

// we cache results for each search conducted for snappy search history navigation
SearchCache = {};

async function getSearch(_query, searchRootNode, cached = true) {
	let searchRootUid = searchRootNode[PROP_UID];
	let queryKey = `(${searchRootUid}) ${_query}`
	if(cached && SearchCache[queryKey])
		return SearchCache[queryKey];
	let serverResponse = await fetchNodes([searchRootUid], PROP_LABEL , 'allofterms', _query, 20);
	let queryObj = { nodes: serverResponse['nodes'] || [], nodelabel: searchRootNode[PROP_LABEL], query: _query };
	SearchCache[queryKey] = queryObj;
	return queryObj;
}

// show/hide the main panes -------------------------------------------------

const D_HIDE = "none";
const D_SHOW = "block";

// get references to the acutal HTML DOM Divs for the panes:
function getPaneDivs(panesOfType, outDict)
{
	for (const [key, value] of Object.entries(panesOfType)) {

		let div = document.getElementById(value.divID);
		if(div)
			outDict[value.divID] = div;
	}
}

// these are lookup tables to get an actual DOM element from a pane type/subtype
var mainPaneDivLookup = {};
var modalPaneDivLookup = {};

getPaneDivs(_panesIndex.view,mainPaneDivLookup);
getPaneDivs(_panesIndex.edit,mainPaneDivLookup);
getPaneDivs(_panesIndex.othermain,mainPaneDivLookup);
getPaneDivs(_panesIndex.add,modalPaneDivLookup);
getPaneDivs(_panesIndex.moveparent,modalPaneDivLookup);
getPaneDivs(_panesIndex.movechildren,modalPaneDivLookup);

// handles displaying a pane type/subtype by hiding the currently visible pane and showing the new one
function switchPane(paneType, paneName)
{
	let _divID = _panesIndex[paneType][paneName].divID;
	
	//main_pane divs
	if(paneType == 'view' || paneType == 'edit' || paneType == 'othermain')
	{
		for (const [key, value] of Object.entries(mainPaneDivLookup))
			value.style.display = (key == _divID) ? D_SHOW : D_HIDE;
	}
	else
	//modal divs
	{
		for (const [key, value] of Object.entries(modalPaneDivLookup))
			value.style.display = (key == _divID) ? D_SHOW : D_HIDE;
		// show the modal div
		toggleModal();
	}
}

// login/auth ------------------------------------------------------------

const BEARERTOKEN = 'bearerToken';
function getBearerToken() {
	return localStorage.getItem(BEARERTOKEN);
}

function getBearerTokenHeader() {
	return 'Bearer '+localStorage.getItem(BEARERTOKEN);
}

function setBearerToken(token) {
	localStorage.setItem(BEARERTOKEN,token);
}

function showLoginModal(showIt)
{
	var loginDivClassList = document.getElementById("modal_div_login").classList;
	if(!showIt && loginDivClassList.contains('is-active'))
		loginDivClassList.remove('is-active');
	else if(showIt) {
		setBearerToken('');
		loginDivClassList.add('is-active');
	}
}

async function doLogin(creds) {

	await fetch('login',{
		method: 'POST',
		headers: {
		  'Content-Type': 'application/json'
		},
		body: JSON.stringify(creds)
	})
	.then(response => { if(!response.ok) { throw new Error(response.status); }; return response.json(); })
	.then(rdata => { 
		if(rdata && rdata['token'] && rdata['token'].length > 0)
		{
			setBearerToken(rdata['token']);
		}
		else
		{
			throw new Error('500');
		}
	})
	.catch(err => {console.log(err);setBearerToken('');});

	if (getBearerToken()) {
		showLoginModal(false);
		if (_lastUpdateTime_Server < 1)
			fetchInitialNodes();
	}
	return (getBearerToken() != '');
}

// event handlers ------------------------------------------------------------

// hide the right-click context menu:
function HideContextMenu(){
	document.getElementById("ctxmenu-div").style.display = "none";
}

// start the spinning wheel logo and mouse pointer animations:
function showLoading(waiting)
{
	let elem = document.getElementById("body_container");
	elem.style.cursor = (waiting) ? "wait" : "auto";
	let logo = document.getElementById("ico-logo");
	let load = document.getElementById("ico-load");
	if(waiting)
	{
		logo.style.display = "none";
		load.style.display = "inline-block";
	}
	else
	{
		load.style.display = "none";
		logo.style.display = "inline-block";
	}
}

// show hide the modal dialog pane:
function toggleModal()
{
   document.getElementById("modal_div").classList.toggle('is-active');
}

function clearFileUploadFormInput()
{
	const fileName = document.getElementById('at_file_name');
      fileName.textContent = 'No File Selected';
}

function clearImportUploadFormInput()
{
	const fileName = document.getElementById('import_file_name');
      fileName.textContent = 'No File Selected';
}

// custom JSON serialization for node objects to be sent in API requests
// strip out certain fields that are only used on the client-side
function serialise(jsonObj) {
    return JSON.stringify(jsonObj, (key,value) =>
	{
		if (key==PROP_PARENTREFS 
			|| key==PROP_CHILDREFS 
			|| key==PROP_LASTMOD 
			|| key == PROP_VUEREF
			|| key == 'isOpen' 
			|| key == 'hasChanged' 
			|| key == 'isViewed' 
			|| key == 'dgraph.type') 
			return undefined;
		//nullify certain values instead of sending empty string, eg. t, x, e, c
		if (value == '' && (
			key==PROP_TEXTDATA 
			|| key==PROP_BINARYDATA 
			|| key==PROP_TIME 
			|| key==PROP_EDITING 
			|| key==PROP_TYPE)) 
			return undefined;
		else return value;
	} );
}

function clearList(list)
{
	if(list)
		while(list.length > 0)
			list.pop()
}

function extendList(list, listToAdd)
{
	if(list && listToAdd)
		listToAdd.forEach(listItem => list.push(listItem));
}


function sortList(list)
{
	//need to do the sorting here because Vue is hanging when using computed or method sorting (maybe an issue with the circular references in/out?)
	list.sort(
		(nodeA,nodeB) => {
			let aType = nodeA[PROP_TYPE];
			let bType = nodeB[PROP_TYPE];
			let aVal = (_typeConfigs[aType] && _typeConfigs[aType].getValueForSorting) ? _typeConfigs[aType].getValueForSorting(nodeA) : nodeA[PROP_LABEL]; 
			let bVal = (_typeConfigs[bType] && _typeConfigs[bType].getValueForSorting) ? _typeConfigs[bType].getValueForSorting(nodeB) : nodeB[PROP_LABEL]; 
			let aIsString = (typeof aVal) === 'string';
			let bIsString = (typeof bVal) === 'string';
			if( aIsString || bIsString ) 
				return (aIsString && bIsString) ? aVal.localeCompare(bVal) : ((aIsString) ? -1 : 1);

			aVal = (isNaN(aVal)) ? Infinity : aVal;
			bVal = (isNaN(bVal)) ? Infinity : bVal;
			return (aVal < bVal) ? -1 : ((aVal > bVal) ? 1 : 0 );
			//^alpha is lower than numeric
		}	
	);
	
}


function clearObjectProperties(obj)
{
	for (var prop in obj) {
		if (obj.hasOwnProperty(prop)) {
			delete obj[prop];
		}
	}
}

// regex to match IP addresses, used for sorting of host nodes in the tree view
const ip_rgx = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/

function convertIPtoNum(ipstr) {
  let octs = ipstr.split('.');
  return (octs[0] * 16777216.0) + (octs[1] * 65536.0) + (octs[2] * 256.0) + octs[3] * 1.0;
}

// this should be modified to return a result that indicates whether there was an error or success
// the result can be interpreted by the 'add' dialog so an error can be shown or the dialog closed if successful
async function upsertGeneric(node)
{	
	showLoading(true);
	await fetch('upsert',{
		method: 'POST',
		headers: {
			'Authorization': getBearerTokenHeader(),
			'Content-Type': 'application/json'
		},
		body: '['+serialise(node)+']' // body data type must match "Content-Type" header
	})
	.then(response => { if(!response.ok) { throw new Error(response.status); }; return response.json(); })
	.then(rdata => { 
		// the API response should be an array of length 1 containing the upserted node's UID
		if(rdata && rdata.length > 0)
		{
			if(!_index[rdata[0]])
				_index[rdata[0]] = emptyNode(rdata[0]);
		}
		else
		{
			throw new Error('500');
		}
	}).catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});
	showLoading(false);

	await refreshNodes();
}


// called from file upload pane onAfterSubmit() hook
// the node may be an empty node (if we're creating a new attachment) or an existing one if overwriting an attachment
async function fileupload(node)
{
	const input = document.getElementById('at_file');

	let params = {};
	if(node[PROP_UID])
		params.attachid = node[PROP_UID];
	params.parentid = node[PROP_PARENTLIST][0].uid;
	
	let data = new FormData();
	data.append('filedata', input.files[0]);
	data.append('type', 'file_upload');
	data.append('_p', JSON.stringify(params));

	await fetch('upload', {
		method: 'POST',
		//mode: 'no-cors', //for testing with httpbin
		//!!important: don't set the content-type
		headers: {
			'Authorization': getBearerTokenHeader()
		},
		body: data
	  }).then(response => { if(!response.ok) { throw new Error(response.status); }; return response.text(); })
	  .then( response => {
			if(response.startsWith('0x'))
			{
				_index[response] = emptyNode(response);
			}
		}).catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});
	
	await refreshNodes();
}


// called from import file upload pane onAfterSubmit() hook
// the node cannot be an empty node because the import needs to be created under a parent node
async function importupload(importer,uid)
{
	showLoading(true);
	const input = document.getElementById('import_file');

	let params = {};
	//if(node[PROP_UID])
	params.under_uid = uid;
	//params.under_uid = node[PROP_PARENTLIST][0].uid;
	
	let data = new FormData();
	data.append('file', input.files[0]);
	data.append('type', 'file_upload');
	data.append('metadata', JSON.stringify(params));

	await fetch('/webservice/import/'+importer, {
		method: 'POST',
		//mode: 'no-cors', //for testing with httpbin
		//!!important: don't set the content-type
		headers: {
			'Authorization': getBearerTokenHeader()
		},
		body: data
	  }).then(response => { if(!response.ok) { throw new Error(response.status); }; return response.text(); })
	  .then( response => {
			if(response.startsWith('0x'))
			{
				_index[response] = emptyNode(response);
			}
		}).catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});
	
	showLoading(false);
	await refreshNodes();
}


// called from generate pane onAfterSubmit() hook
// the node cannot be an empty node because the generated node needs to be created under a parent node
async function generate(generator,serialized_params, uid)
{
	showLoading(true);

	let params = JSON.parse(serialized_params);//{};
	//if(node[PROP_UID])
	params.under_uid = uid;
	params.generator = generator;
	//params.under_uid = node[PROP_PARENTLIST][0].uid;
	
	let data = JSON.stringify(params);

	await fetch('/webservice/generate/'+generator, {
		method: 'POST',
		//mode: 'no-cors', //for testing with httpbin
		//!!important: don't set the content-type
		headers: {
			'Authorization': getBearerTokenHeader()
		},
		body: data
	  }).then(response => { if(!response.ok) { throw new Error(response.status); }; return response.text(); })
	  .then( response => {
			if(response.startsWith('0x'))
			{
				_index[response] = emptyNode(response);
			}
		}).catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});
	
	showLoading(false);
	await refreshNodes();
}


// implements drag and drop nodes to a different parent node
async function moveNodeToNewParent(node, newParentNode)
{	
	let existingParentUids = []
	node[PROP_PARENTREFS].forEach(n => existingParentUids.push(n[PROP_UID]));
	
	let moveData = {
		nodes: [node[PROP_UID]],
		parents: existingParentUids,
		children: [],
		newparent: newParentNode[PROP_UID]
	}
	showLoading(true);

	await fetch('move',{
		method: 'POST',
		headers: {
			'Authorization': getBearerTokenHeader(),
		  'Content-Type': 'application/json'
		},
		body: JSON.stringify(moveData) // body data type must match "Content-Type" header
	})
	.then(response => { if(!response.ok) { throw new Error(response.status); }; return response.json(); })
	.then(rdata => { 
		if(rdata && rdata.error)
		{
			console.log("move nodes failed: ",rdata.message);//need to deal with any errors
		}
	})
	.catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});
	showLoading(false);

	await refreshNodes();
}

// implements clone node functionality
async function copyNodeToParent(node, newParentNode)
{	
	let newCopy = emptyNode();
	updateNode(newCopy, node);
	newCopy[PROP_PARENTLIST] = [{uid: newParentNode[PROP_UID]}];
	newCopy[PROP_CHILDLIST] = [];
	newCopy[PROP_UID] = '';
	//todo: remember to nuke lnk[] too when implemented
	await upsertGeneric(newCopy);
}



// functionality for refreshing node state/updates
// we send a list of node uids to the server and it will return a subset of those nodes modified since the last refresh timestamp

var _lastUpdateTime_Server = 0;
var _lastUpdateTime_Browser = Date.now();

function setLastUpdatedTime(serverTimestamp) {
	_lastUpdateTime_Server = serverTimestamp;
	_lastUpdateTime_Browser = Date.now();
}

// fetch all node UIDs from the master index
function getUidsFromIndex()
{
	let listOfUids = [];
	for (const [key, value] of Object.entries(_index)) {
		listOfUids.push(key);
	}
	return listOfUids;
}

// compare whether a list of the latest node UIDs received from server is the same as the existing state so we can fetch data for any new nodes from the server
function refsAndListContainSameUids(refs, list)
{
	if (refs.length != list.length)
		return false;
	let refsSet = new Set(refs);
	for (let i=0; i < list.length; i++)
		if(!refsSet.has(list[i][PROP_UID]))
			return false;
	return true;
}

// if nodeid's children have changed, we fetch them from the server
async function fetchChildNodes(nodeid)
{
	let node = _index[nodeid];
	if( node 
		&& (node[PROP_CHILDLIST].length) 
		&& !refsAndListContainSameUids(node[PROP_CHILDLIST], node[PROP_CHILDREFS]))
		await fetchNodes([nodeid],PROP_LASTMOD,'gt',0,1);
}


async function refreshNodes()
{
	await fetchNodes(getUidsFromIndex());
}

async function fetchInitialNodes()
{
	setLastUpdatedTime(0);
	//this will fetch only the root node:
	await fetchNodes(null,PROP_LASTMOD,'gt',0,0);
	//there should be only two nodes in the index after this initial request:
	// _index['.'] (the placeholder for root node)
	// _index['0xN'] (the actual root node
	for (const [key, value] of Object.entries(_index)) {
		if(key != '.') {
			updateNode(G.root,value);
			createEdgesForNode(G.root);
			delete _index['.'];
			_index[G.root[PROP_UID]] = G.root;
		}
	}
	await fetchChildNodes(G.root.uid,0);
}

// call the API to get nodes modified since the last refresh
async function fetchNodes(_uids, _field = PROP_LASTMOD, _op = 'gt', _val = _lastUpdateTime_Server, _depth = 0)
{
	let data = { field: _field, op: _op, val: `${_val}`, depth: _depth, uids: _uids };
	let serverResp = {};
	showLoading(true);

	await fetch('/nodes', {
		method: 'POST',
		//mode: 'no-cors', //for testing with httpbin
		headers: {
			'Authorization': getBearerTokenHeader(),
		  'Content-Type': 'application/json'
		},
		body: JSON.stringify(data)
	})
	.then(response => { if(!response.ok) { throw new Error(response.status); }; return response.json(); })
	.then(rdata => { 
		serverResp = rdata;
		if(rdata && rdata.nodes && !rdata.error)
		{
			updateNodeTree(rdata);
		}
		else
		{	
			throw new Error('500');
		}
	})
	.catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});
	showLoading(false);	
	return serverResp;
}

// this is deprecated, we should remove it
function createEdgesFromUids(listUidObjs)
{
	let tmpList = [];
	if(listUidObjs)
		listUidObjs.forEach(uidobj => {
			if(_index[uidobj.uid]) 
				tmpList.push(_index[uidobj.uid]);
		});
	return tmpList;
}

// generate object references for the parent/child nodes for a node given a list of UIDs, and push those references onto a list 
function createEdgesFromUidsInplace(listUidObjs,existingList)
{
	if(listUidObjs)
		listUidObjs.forEach(uidobj => {
			if(_index[uidobj.uid]) 
				existingList.push(_index[uidobj.uid]);
		});
}


// on the client-side, to make things easier, we store a list of object references for parent/child nodes in a given node
// this is in addition to the dgraph list of parent and child node UIDs (PROP_PARENTLIST and PROP_CHILDLIST)
function createEdgesForNode(node)
{
		//root node doesn't have parentrefs, what to do?
		clearList(node[PROP_PARENTREFS]);
		createEdgesFromUidsInplace(node[PROP_PARENTLIST],node[PROP_PARENTREFS]);

		clearList(node[PROP_CHILDREFS]);
		createEdgesFromUidsInplace(node[PROP_CHILDLIST],node[PROP_CHILDREFS]);

		///*************
		// the sorting of child references (for ordering in the the tree-view) was done here because using VueJS computed/methods was hanging,
		// so we sort them during edge creation as a workaround.
		///*************
		sortList(node[PROP_CHILDREFS]);
		if(node[PROP_PARENTREFS] && node[PROP_PARENTREFS].length) {
			node[PROP_PARENTREFS].forEach( parent => sortList(parent[PROP_CHILDREFS]) );
		}
}

// update an existing node in the master index with the latest data returned from the server
function updateNode(existingNode, updatedNode)
{
	//  assumptions we can safely make: 
	//  queryNodes always returns uid, label, detail, customdata, time, editing, lastmod, in, out *if* they are present
	//  so, if any of these are not present, then they are null. 
	//  we don't want to create fields if they don't already exist *except* for in, out
	//  if in or out don't exist then create empty arrays

	let oldHasChangedValue = existingNode.hasChanged;
	
	existingNode.hasChanged = (updatedNode[PROP_LASTMOD] != existingNode[PROP_LASTMOD]); 
	
	if(existingNode.isViewed && existingNode.hasChanged)
		existingNode.isViewed = false;
		
	for (const [key, value] of Object.entries(updatedNode)) {
	  existingNode[key] = value;
	}
}

// the server response should contain nodes that have been modified since the last refresh
// update the node data in the master index
function updateNodeTree(serverResponse)
{

	let nodes = serverResponse.nodes;
	for (let i = 0; i < nodes.length; i++)
	{
		//  if the node already exists in mainindex then update
		let incomingNode = nodes[i];

		incomingNode[PROP_PARENTLIST] = incomingNode[PROP_PARENTLIST] || [];
		incomingNode[PROP_PARENTREFS] = incomingNode[PROP_PARENTREFS] || [];
		incomingNode[PROP_CHILDLIST] = incomingNode[PROP_CHILDLIST] || [];
		incomingNode[PROP_CHILDREFS] = incomingNode[PROP_CHILDREFS] || [];
		incomingNode[PROP_RELATIONS] = incomingNode[PROP_RELATIONS] || [];

		let tnode = _index[incomingNode.uid];

		if(tnode)
			updateNode(tnode, incomingNode);
		else
		{
			incomingNode.hasChanged = true;
			incomingNode.isViewed = false;
			incomingNode.isOpen = false;
			incomingNode.showChildren = _typeConfigs[incomingNode[PROP_TYPE]].showChildren; 
			_index[incomingNode.uid] = incomingNode;
		}
	}

	for (let i = 0; i < nodes.length; i++)	
		createEdgesForNode(_index[nodes[i].uid]);

	setLastUpdatedTime(serverResponse.timestamp);
	//vue_col_groups.$forceUpdate();
}

// called from the onBeforeCopyNode() hook for the Note, Code and Table types
// because the node data returned by the server (eg. for bulk updates or when a tree-view branch is expanded) doesnt contain large fields like textdata or blobdata
// the node being edited/viewed needs to make another request to the API to fetch the missing (or updated) text/blob data.
async function updateAttachmentNodeIfChangedOrEmpty(node,datafield = PROP_TEXTDATA)
{
	if(node.hasChanged || !node[datafield])
	{
		showLoading(true);
		await fetch('/attachment/'+node[PROP_UID]+'/0',{headers:{'Authorization': getBearerTokenHeader()}})
		.then(response => { if(!response.ok) { throw new Error(response.status); }; return response.json(); })
		.then(data => { 
			updateNodeTree(data);
			}
		)
		.catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});
		showLoading(false);
	}
	else {console.log("att hasnt changed or already has datafield: ",node.hasChanged,node[datafield]);}
}

// because the /download endpoint is hyperlinked in the view for attachment download (we want a direct hyperlink to save-as or open in a new window), 
// we have to put some kind of auth in the URL
async function getSignedDownloadUrl(attachmentUid) {

	let queryString = '?';

	await fetch('/downloadtoken/'+attachmentUid,{headers:{'Authorization': getBearerTokenHeader()}})
	.then(response => { if(!response.ok) { throw new Error(response.status); }; return response.json(); })
	.then(rdata => { 
		if(rdata && rdata['sig'] && rdata['sig'].length > 0)
		{
			let sigEncoded = encodeURIComponent(rdata['sig']);
			queryString += `sig=${sigEncoded}&exp=${rdata.exp}&non=${rdata.non}`;
		}
		else
		{
			throw new Error('500');
		}
	})
	.catch(err => {console.log(err); if(err.message == '401') showLoginModal(true);});

	return '/download/'+attachmentUid+queryString;
}

/////////////////////////////////////////////////////////////////////////////////////////
//     VueJS Bindings
/////////////////////////////////////////////////////////////////////////////////////////

// event handler for start dragging UI component
function startDragging(evt, id, action) {
	evt.dataTransfer.dropEffect = action;
	evt.dataTransfer.effectAllowed = action;
	evt.dataTransfer.setData('action', action);
	evt.dataTransfer.setData('itemID', id);
}

// define the tree-item UI component
Vue.component("tree-item", {
	template: "#item-template",
	props: {
	  item: Object ,   //these properties can be accessed/modified externally, as well as in computed/methods (refer to it using this.item)
	  depth: Number
	},
	data: function() {  //component instance's initial state is obtained from here, refer to data in methods/computed using this.isOpen
	  return {
		isOpen: false,
	  };
	},
	mounted: function() {
		this.item[PROP_VUEREF] = this;
	},
	computed: {
	  //you can have some additional logic when displaying name (eg. truncating, combining label + detail)
	  getIndent: function() {
		return (this.depth * 10) + 'px';
	  },
	},
	methods: {
		getIcon: function() { // calculate the icon to use based on the node type
			if(!_typeConfigs[this.item[PROP_TYPE]])
				return 'ico-miscfile';
			return _typeConfigs[this.item[PROP_TYPE]].iconClassName || 'ico-miscfile';
		},
		showCtxMenu: function (event,nodeID) { //right-click on the tree-item will show a floating context menu
			  contextMenuFor("ctxmenu-div",event,nodeID);
		},
		viewNode: function(e, id) { //left click opens the node details in the main pane
			if (historyPush(HISTORY_VIEWNODE,id))
				v_action_funcs['view'](id);
		},
		toggle: function(id) { // expand/close the tree item
			if (this.hasChildren) {
			  if(!this.isOpen) 
				fetchChildNodes(id);
			  this.isOpen = !this.isOpen;
			}
		},
	    hasChildren: function() {
			return this.item[PROP_CHILDLIST] && this.item[PROP_CHILDLIST].length;
		},
		isCurrentlySelected: function() {
			return this.item[PROP_UID] == v_currently_selected_node.node[PROP_UID];
		},
		name: function() {
			return this.item[PROP_LABEL];
		},
		startDrag: function(evt, id) {
			startDragging(evt, id, 'move');
		},
		onDrop: async function (evt) {
			const srcNodeID = evt.dataTransfer.getData('itemID');
			const action = evt.dataTransfer.getData('action');

			if(action == 'copy')
				await v_action_funcs['copy'](srcNodeID,this.item[PROP_UID]);
			else
				await v_action_funcs['move'](srcNodeID,this.item[PROP_UID]);
		},
	}
});


// the top-level tree-view component
var v_tree_pane = new Vue({
	el: "#v_tree_pane",
	data: {
	  treeData: G
	},
	methods: {
	}
});

// dynamically create the right-click context menu based on the type of node, as the menu options differ for each
// _typeConfigs stores the definitions for each node type and the context menus are determined by what child nodes are allowed to be added
// calculates the x,y coords to render the floating div 
function contextMenuFor(ctxmenudiv,event,nodeID)
{
	event.preventDefault();

	let n = _index[nodeID];

	if(n) {
		G.ctxmenuData = emptyCtxMenuData(n[PROP_UID]);

		let nConfig = _typeConfigs[n[PROP_TYPE]] || _typeConfigs['unknown'];

		if(nConfig.actionEditConf)
			G.ctxmenuData.mainOptions.push("edit");

		let allowedToAdd = Array.from(nConfig.typesAllowedForChildNodes || []);
		allowedToAdd.forEach((typename,index) => {G.ctxmenuData.addOptions.push(`+${typename}`)});

		let menu = document.getElementById(ctxmenudiv);
		menu.style.left = event.pageX + 'px';
		menu.style.top = event.pageY + 'px';
		menu.style.display = 'block';

	}
	//nodeID was not found, no context menu to show
	return;
}

// the config info to render the context menu consists of the following:
// {uid:'0x345',mainOptions:['edit','move'],addOptions:['+foo','+bar']}
function emptyCtxMenuData(_uid = '.') {
	return {uid: _uid, mainOptions: [], addOptions: []};
}


// these are action handlers triggered by events such as left-clicking a node, selecting "add <nodetype>", "edit" etc.
// the handlers are generic and will execute shared code for fetching node data from the index, switching view panes, etc.
// they will then call custom hooks/callbacks for the node type, which are defined in _panesIndex
var v_action_funcs = { 
	view: async function (uid) { 
		let n = _index[uid];
		let tc = _typeConfigs[(n[PROP_TYPE] || "unknown")] || _typeConfigs.unknown;
		if(tc) {
			let conf =  tc.actionViewConf || _typeConfigs.unknown.actionViewConf;
			_panesIndex.view[conf.paneType].v.config = conf.config;
			_panesIndex.view[conf.paneType].v.config.nodeinfo = _index[uid];
			await _panesIndex.view[conf.paneType].onBeforeShow();
			switchPane('view',conf.paneType);
			n.isViewed = true;
			v_currently_selected_node.node = n;
			if(n[PROP_PARENTREFS]) {
				n[PROP_PARENTREFS][0][PROP_VUEREF].isOpen = true;
			}
		}
	},
	add: async function (typenameOfNew, _uid) { 
		let tc = _typeConfigs[typenameOfNew];
		if(tc) {
			let conf =  tc.actionAddConf || _typeConfigs.unknown.actionAddConf;
			_panesIndex.add[conf.paneType].v.config = conf.config;
			let newN = emptyNode('',typenameOfNew);
			newN[PROP_PARENTLIST].push({uid: _uid});
			_panesIndex.add[conf.paneType].v.config.nodeinfo = newN;
			await _panesIndex.add[conf.paneType].onBeforeShow();
			switchPane('add',conf.paneType);
		}
	},
	import: async function (_uid) { 		
		_panesIndex.add['importupload'].v.config.under_uid = _uid;
		//_panesIndex.add['importupload'].v.config.importer = 'example';
		await _panesIndex.add['importupload'].onBeforeShow();
		switchPane('add','importupload');
	},
	generate: async function (generator,_uid) { 		
		_panesIndex.add['generator'].v.config.under_uid = _uid;
		_panesIndex.add['generator'].v.config.generator = generator;
		//_panesIndex.add['importupload'].v.config.importer = 'example';
		await _panesIndex.add['generator'].onBeforeShow();
		switchPane('add','generator');
	},
	edit: async function (uid) { 
		let n = _index[uid];
		let tc = _typeConfigs[(n[PROP_TYPE] || "unknown")] || _typeConfigs.unknown;
		if(tc) {
			let conf =  tc.actionEditConf || _typeConfigs.unknown.actionEditConf;
			_panesIndex.edit[conf.paneType].v.config = conf.config;
			
			if(_panesIndex.edit[conf.paneType].onBeforeCopyNode) {
				_panesIndex.edit[conf.paneType].v.config.nodeinfo = n;
				await _panesIndex.edit[conf.paneType].onBeforeCopyNode();
			}			
			let tmpNodeCopy = emptyNode(n[PROP_UID]);
			tmpNodeCopy[PROP_LABEL] = n[PROP_LABEL] || null;
			tmpNodeCopy[PROP_DETAIL] = n[PROP_DETAIL] || null;
			tmpNodeCopy[PROP_CUSTOM] = n[PROP_CUSTOM] || null;
			tmpNodeCopy[PROP_TEXTDATA] = n[PROP_TEXTDATA] || null;
			tmpNodeCopy[PROP_TIME] = n[PROP_TIME] || null;
			tmpNodeCopy.hasChanged = n.hasChanged;
			_panesIndex.edit[conf.paneType].v.config.nodeinfo = tmpNodeCopy;
			
			if(historyPush(HISTORY_VIEWNODE,n[PROP_UID])) {
				v_currently_selected_node.node = n;
				await _panesIndex.edit[conf.paneType].onBeforeShow();
				switchPane('edit',conf.paneType);
				n.isViewed = true;
			}
		}
	},
	search: async function(queryData, cached = true) { 
		queryresults = await getSearch(queryData.query, queryData.node, cached);
		_panesIndex.othermain.search.v.config.results = queryresults;
		switchPane('othermain','search');
	},
	copy: async function (srcUID, targetUID) { 

		//reject obvious stuff: src and target are same, and can't move the root node
		if(srcUID == targetUID)
		{
			notification('Can\'t copy to same item');
			return;
		}

		if(srcUID == G.root[PROP_UID])
		{
			notification('Can\'t copy the root element');
			return;
		}

		let nSrc = _index[srcUID];
		let nTarget = _index[targetUID];

		
		//check whether target type allows children of src type and reject if not so
		let targetTC = _typeConfigs[nTarget[PROP_TYPE]];
		if(!targetTC.typesAllowedForChildNodes.has(nSrc[PROP_TYPE]))
		{
			notification(`${nSrc.ty}s are not allowed to be added to ${nTarget.ty}s`);
			return;
		}

		//do the copy:
		await copyNodeToParent(nSrc, nTarget);
	},	
	move: async function (srcUID, targetUID) { 

		//reject obvious stuff: src and target are same, and can't move the root node
		if(srcUID == targetUID)
		{
			notification('The source and destination are the same');
			return;
		}

		if(srcUID == G.root[PROP_UID])
		{
			notification('Can\'t move the root element');
			return;
		}

		let nSrc = _index[srcUID];
		let nTarget = _index[targetUID];


		//check if target is already the direct parent of src and reject if so
		if(nSrc[PROP_PARENTREFS] && (nSrc[PROP_PARENTREFS].filter(e => e[PROP_UID] == nTarget[PROP_UID]).length > 0))
		{
			return;
		}
		
		//check whether target type allows children of src type and reject if not so
		let targetTC = _typeConfigs[nTarget[PROP_TYPE]];
		if(!targetTC.typesAllowedForChildNodes.has(nSrc[PROP_TYPE]))
		{
			notification(`${nSrc.ty}s are not allowed to be added to ${nTarget.ty}s`);
			return;
		}
		
		//check for creation of a cycle and reject if so
		//**This also needs to be implemented on the server side to prevent DoS
		if(checkIfLinkCreationCausesCycle(nTarget,nSrc))
		{
			console.log(`adding "${nSrc[PROP_LABEL]}" as child of "${nTarget[PROP_LABEL]}" would create a cyclic reference`);
			return;
		}

		//do the move:
		await moveNodeToNewParent(nSrc, nTarget);
	},
};

// if adding child to parent, will a cycle be created?
function checkIfLinkCreationCausesCycle(intendedParentNode,tmpTraverseNode) {
	if(!tmpTraverseNode || !tmpTraverseNode[PROP_CHILDREFS])
		return false;
	if(tmpTraverseNode[PROP_UID] == intendedParentNode[PROP_UID])
		return true;
	let result = false;
	tmpTraverseNode[PROP_CHILDREFS].forEach(childN => { result = result || checkIfLinkCreationCausesCycle(intendedParentNode, childN)});
	return result;
}

// right-click context menu component for tree-items
var v_ctxmenu = new Vue({
	el: "#v_ctxmenu",
	data: {
	  vdata: G
	},
	methods: {
		ctxmenuAction: function (e, ac, uid) {
			if(ac.startsWith('+')) {
				v_action_funcs['add'](ac.substring(1),uid);
			}
			else
				v_action_funcs[ac](uid);
		}
	}
});


// "save" button click event handler
function handleSubmit(ac, pane) {
	_panesIndex[ac][pane].onAfterSubmit();
	if(ac != 'view' && ac != 'edit')
		toggleModal();
}

// called when data has been changed in an editor view
function handleValueChanged() {
	warnOnNavigateAway = true;
}

// search results page vue component
var v_othermain_search = new Vue({
	el: '#v_othermain_search',
	data: { 
	   v: _panesIndex['othermain']['search'].v
	},
	computed: {
	},
	methods : {
        getTypeIcon: function (node) {
			let type = node[PROP_TYPE] || 'unknown';
			let tConf = _typeConfigs[type];
			return (tConf) ? tConf.iconClassName : 'ico-miscfile';
        }, 
		viewNode: function(e, id) {
			if(historyPush(HISTORY_VIEWNODE,id))
				v_action_funcs['view'](id);
		},
	}
});

// default main pane view component
var v_view_default = new Vue({
	el: '#v_view_default',
	data: { 
	   v: _panesIndex['view']['default'].v
	},
	computed: {
	},
	methods : {
        getTypeIcon: function (node) {
			let type = node[PROP_TYPE] || 'unknown';
			let tConf = _typeConfigs[type];
			return (tConf) ? tConf.iconClassName : 'ico-miscfile';
        }, 
        loadChildren: function (id) {
			fetchChildNodes(id);
        }, 
		viewNode: function(e, id) {
			if(historyPush(HISTORY_VIEWNODE,id))
				v_action_funcs['view'](id);
		},
		//clickImport($event,v.config.nodeinfo.uid)
		clickImport: function(e, id) {
			if(historyPush(HISTORY_VIEWNODE,id))
				v_action_funcs['import'](id);
		},
		clickGenerate: function(e, gen_id, uid) {
			v_action_funcs['generate'](gen_id,uid);
		},
		startDrag: function(evt,id) {
			startDragging(evt, id, 'move');
		},
		onDrop: async function (evt) {
			const srcNodeID = evt.dataTransfer.getData('itemID');
			const action = evt.dataTransfer.getData('action');
			let item = this.v.config.nodeinfo;
			if(action == 'copy')
				await v_action_funcs['copy'](srcNodeID,item[PROP_UID]);
			else
				await v_action_funcs['move'](srcNodeID,item[PROP_UID]);
		},
	}
});


// findings main pane view component
var v_view_findings = new Vue({
	el: '#v_view_findings',
	data: { 
	   v: _panesIndex['view']['findings'].v
	},
	computed: {
	},
	methods : {
        getTypeIcon: function (node) {
			let type = node[PROP_TYPE] || 'unknown';
			let tConf = _typeConfigs[type];
			return (tConf) ? tConf.iconClassName : 'ico-miscfile';
        }, 
        loadChildren: function (id) {
			fetchChildNodes(id);
        }, 
		viewNode: function(e, id) {
			if(historyPush(HISTORY_VIEWNODE,id))
				v_action_funcs['view'](id);
		},
		startDrag: function(evt,id) {
			startDragging(evt, id, 'move');
		},
		onDrop: async function (evt) {
			const srcNodeID = evt.dataTransfer.getData('itemID');
			const action = evt.dataTransfer.getData('action');
			let item = this.v.config.nodeinfo;
			if(action == 'copy')
				await v_action_funcs['copy'](srcNodeID,item[PROP_UID]);
			else
				await v_action_funcs['move'](srcNodeID,item[PROP_UID]);
		},
	}
});

// file attachment view component
var v_view_download = new Vue({
	el: '#v_view_download',
	data: { 
	   v: _panesIndex['view']['download'].v
	},
	methods : {
		vOpenNewWindow :  async function(uid){ 
			let url = await getSignedDownloadUrl(uid);
			openNewWindow(url);
		},
		vGetImgDataURI : function() {
			return "data:image;base64," +  this.v.config.nodeinfo[PROP_BINARYDATA];
		},
		vOpenImageNewWindow : async function(uid){
			openNewWindow('',this.vGetImgDataURI());
		}
	}
});

// tool output / textdata view component
var v_view_textbody = new Vue({
	el: '#v_view_textbody',
	data: { 
	   v: _panesIndex['view']['textbody'].v
	},
	methods : {
		vCustom :  function(x){ 
		}
	}
});

// tool output / textdata view component
var v_view_json = new Vue({
	el: '#v_view_json',
	data: { 
	   v: _panesIndex['view']['json'].v
	},
	methods : {
		vCustom :  function(x){ 
		}
	}
});

// default node edit component
var v_edit_default = new Vue({
	el: '#v_edit_default',
	data: { 
	   v: _panesIndex['edit']['default'].v
	},
	methods : {
        getTypeName: function (id) {
			return _index[id][PROP_TYPE];
        }, 
		vSubmit :  function(){ 
			handleSubmit('edit', 'default');
		},
		vCancel :  function(){ 
			navigateMainPaneBack();
		},
		vChanged :  function(){ 
			handleValueChanged();
		}
	}
});

// task edit component
var v_edit_task = new Vue({
	el: '#v_edit_task',
	data: { 
	   v: _panesIndex['edit']['task'].v
	},
	methods : {
		vSubmit :  function(){ 
			handleSubmit('edit', 'task');
		},
		vCancel :  function(){ 
			navigateMainPaneBack();
		},
		vChanged :  function(){ 
			handleValueChanged();
		}
	}
});

// temp task/agent node edit component
var v_testform = new Vue({
	el: '#v_testform',
	data: { 
	   v: _panesIndex['edit']['testtaskagent'].v
	},
	methods : {
        getTypeName: function (id) {
			return _index[id][PROP_TYPE];
        }, 
		vSubmit :  function(){ 
			handleSubmit('edit', 'testtaskagent');
		},
		vCancel :  function(){ 
			navigateMainPaneBack();
		},
		vChanged :  function(){ 
			handleValueChanged();
		}
	}
});


// login form component
var v_loginform = new Vue({
	el: '#v_loginform',
	data: { 
	   v: { username: '', password: ''},
	   other: { message: '' }
	},
	methods : {
		vSubmit :  function(){ 
			doLogin(this.v).then( loginSuccess => {
				this.other.message = (!loginSuccess) ? 'Login Failed' : '';
				if(loginSuccess)
					this.v.password = '';
			})
		}
	}
});

// generic "add node" dialog component
var v_add_default = new Vue({
	el: '#v_add_default',
	data: { 
	   v: _panesIndex['add']['default'].v
	},
	methods : {
		vSubmit :  function(){ 
			handleSubmit('add', 'default');
		}
	}
});


// "add note" dialog component
var v_add_editor = new Vue({
	el: '#v_add_editor',
	data: { 
	   v: _panesIndex['add']['editor'].v
	},
	methods : {
		vSubmit :  function(){ 
			handleSubmit('add', 'editor');
		}
	}
});

// "add table" dialog component
var v_add_table = new Vue({
	el: '#v_add_table',
	data: { 
	   v: _panesIndex['add']['table'].v
	},
	methods : {
		vSubmit :  function(){ 
			handleSubmit('add', 'table');
		}
	}
});


// "add task" dialog component
var v_add_task = new Vue({
	el: '#v_add_task',
	data: { 
	   v: _panesIndex['add']['task'].v
	},
	methods : {
		vSubmit :  function(){ 
			handleSubmit('add', 'task');
		}
	}
});


// "view/edit note" component
var v_all_editor = new Vue({
	el: '#v_all_editor',
	data: { 
	   v: _panesIndex['edit']['editor'].v,
	   q: quillGlobal
	},
	methods : {
		startDrag: function(evt) {
			startDragging(evt, this.q.CurrentUid, 'copy');
		},
	}
});

// "view/edit code" component
var v_codeedit_title = new Vue({
	el: '#v_codeedit_title',
	data: { 
	   v: _panesIndex['view']['codeedit'].v,
	},
	methods : {
	}
});


// "view/edit table" component
var v_all_table = new Vue({
	el: '#v_all_table',
	data: { 
	   v: _panesIndex['edit']['table'].v,
	   j: jexcelGlobal
	},
	methods : {
		startDrag: function(evt) {
			startDragging(evt, this.j.CurrentUid, 'copy');
		},
	}
});

// "upload file" component
var v_add_fileupload = new Vue({
	el: '#v_add_fileupload',
	data: { 
	   v: _panesIndex['add']['fileupload'].v,
	   filename: 'No File Selected'
	},
	methods : {
        vUpdateFileName: function () {
			const fileInput = document.getElementById("at_file");
			if (fileInput.files.length > 0) {
				const fileName = document.getElementById('at_file_name');
				fileName.textContent = fileInput.files[0].name;
			}
        }, 
		vSubmit :  function(){ 
			handleSubmit('add', 'fileupload');
		}
	}
});

// "import file" component
var v_import_fileupload = new Vue({
	el: '#v_import_fileupload',
	data: { 
	   v: _panesIndex['add']['importupload'].v,
	   filename: 'No File Selected',
	   options: ['example','nmap','sarif210','srccode']
	},
	methods : {
        vUpdateFileName: function () {
			const fileInput = document.getElementById("import_file");
			if (fileInput.files.length > 0) {
				const fileName = document.getElementById('import_file_name');
				fileName.textContent = fileInput.files[0].name;
			}
        }, 
		vSubmit :  function(){ 
			handleSubmit('add', 'importupload');
		}
	}
});

var v_add_generator = new Vue({
	el: '#v_add_generator',
	data: { 
	   v: _panesIndex['add']['generator'].v
	},
	methods : {
		vSubmit :  function(){ 
			handleSubmit('add', 'generator');
		}
	}
});


var v_currently_selected_node = { node: G.root };

// top navigation bar component
var vue_topnav = new Vue({
	el: '#v_topnav',
	data: { 
	   v: v_currently_selected_node,
	   iconBack: 'ico-left-arr-dis',
	   iconFwd: 'ico-right-arr-dis',
	},
	computed: {
		getLabel: function() {
			let label = this.v.node[PROP_LABEL];
			return (label.length > 48) ? label.substring(0,48)+'...' : label;
		}
	},
	methods: {
		vSync: async function() {
			await refreshNodes();
		},
		vNavBack: function() {
			navigateMainPaneBack();
		},
		vNavFwd: function() {
			navigateMainPaneForward();
		},		
		vNavUp: async function() {
			let n = v_currently_selected_node.node;
			console.log('vNavUp',n)
			if(n[PROP_PARENTLIST] && n[PROP_PARENTLIST].length > 0) {
				let id = n[PROP_PARENTLIST][0][PROP_UID];
				console.log('vNavUp id ',id)

				if( !(id in _index) )
					await fetchNodes([id],PROP_LASTMOD,'gt',0,1);

				if(historyPush(HISTORY_VIEWNODE,id))
					v_action_funcs['view'](id);
			}
		},
	}
});

// top search bar component
var vue_topsearch = new Vue({
	el: '#v_topsearch',
	data: { 
	   v: v_currently_selected_node,
	   query: '',
	},
	methods: {
		vDoSearch: async function() {
			let queryObj = {query: this.query, node: this.v.node};
			if(historyPush(HISTORY_SEARCH, queryObj))
				await v_action_funcs['search'](queryObj, false);
		},
		
	}
});


var vue_bottom_bar = new Vue({
	el: '#v_bottom_bar',
	data: { 
	   v: v_currently_selected_node,
	},
	methods: {		
	}
});
////////////////////////////////////////////////////
//   resizable pane javascript
////////////////////////////////////////////////////

let isLeftDragging = false;
let isRightDragging = false;

function ResetColumnSizes() {
  // when page resizes return to default col sizes
  let page = document.getElementById("pageFrame");
  page.style.gridTemplateColumns = "2fr 6px 6fr";
}

function SetCursor(cursor) {
  let page = document.getElementById("page");
  page.style.cursor = cursor;
}

function StartLeftDrag() {
  isLeftDragging = true;
  SetCursor("ew-resize");
}

function StartRightDrag() {
  isRightDragging = true;
  SetCursor("ew-resize");
}

function EndDrag() {
  isLeftDragging = false;
  isRightDragging = false;
  SetCursor("auto");
}

function OnDrag(event) {
  if (isLeftDragging || isRightDragging) {

    let page = document.getElementById("page");
    let left_pane = document.getElementById("left_pane");

    let leftPaneWidth = isLeftDragging ? event.clientX : left_pane.clientWidth;

    let dragbarWidth = 6;

    let cols = [
      leftPaneWidth,
      dragbarWidth,
      page.clientWidth - dragbarWidth - leftPaneWidth,
    ];

    let newColDefn = cols.map(c => c.toString() + "px").join(" ");

    page.style.gridTemplateColumns = newColDefn;

    event.preventDefault()
  }
}


//////////////////////////////////////////////////////////////////
//   main execution loop, initialise and refresh every 60secs
//////////////////////////////////////////////////////////////////

if (getBearerToken() == '')
	showLoginModal(true);
else
	fetchInitialNodes();


const SLEEPINTERVAL = 60000; //millisec
var sleepTime = SLEEPINTERVAL;

setInterval( () => {
	let timeNow = Date.now();
	if(timeNow >=  (_lastUpdateTime_Browser + SLEEPINTERVAL)) {
		refreshNodes();
		sleepTime = SLEEPINTERVAL;
	}
	else {
		sleepTime = (_lastUpdateTime_Browser + SLEEPINTERVAL) - timeNow;
	}
},sleepTime);
