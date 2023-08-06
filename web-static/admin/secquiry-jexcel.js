// jexcel ------------------------------------------------------------

var jexcelGlobal = { CurrentUid: '' };

var j_initial_cols = [{type: 'text', title:'A',width:100},{type: 'text', title:'B',width:100}] ;
var j_initial_data = [{0:'',1:''},{0:'',1:''}];

var j = jexcel(document.getElementById('jexcel'), {
 data: j_initial_data,
 columns: j_initial_cols
}
);

var j_isEnabled = false;
function toggleJexcel()
{
	if(j_isEnabled)
		_panesIndex['edit']['table'].onAfterSubmit();
	else
		v_action_funcs['edit'](jexcelGlobal.CurrentUid);
	j_isEnabled = !j_isEnabled;
}

function setJexcelReadonly(readonly = true)
{
	let jconf = j.getConfig();
	jconf.columns.forEach(column => column.readOnly = readonly);
	//reload to show updated state
	j.setData(null);
}

function populateJexcel(nodeinfo)
{
	let serialisedData = nodeinfo[PROP_TEXTDATA] ||  '{"jsondata":null,"jsoncols":null}';
//console.log('Jexcel serialisedData',serialisedData);
	let jdata = JSON.parse(serialisedData);
	let rowdata = JSON.parse(jdata.jsondata) || j_initial_data;
	let coldata = JSON.parse(jdata.jsoncols) || j_initial_cols;

	j.destroy();
	j = jexcel(document.getElementById('jexcel'), {
        data: rowdata,
        columns: coldata
    });

	let edtitle = document.getElementById('table_title');
	edtitle.value = nodeinfo[PROP_LABEL];
}

function getJexcelEdits(nodeinfo)
{
	let edtitle = document.getElementById('table_title');
	let jdata = {};
	jdata.jsondata = JSON.stringify(j.getConfig().data);
	jdata.jsoncols = JSON.stringify(j.getConfig().columns);
	//yep, they're serialised json inside serialised json
	nodeinfo[PROP_TEXTDATA] = JSON.stringify(jdata);
	nodeinfo[PROP_LABEL] = edtitle.value;
	nodeinfo[PROP_DETAIL] = 'Table';
}

function setJexcelVisualState(status)
{
	let edbutton = document.getElementById('toggleEditingTable');
	let edtitle = document.getElementById('table_title');

	if(status == 'enable') {
		setJexcelReadonly(false);
		edtitle.readOnly = false;
		edbutton.innerText = "Save";
	}
	else {
		setJexcelReadonly(true);
		edtitle.readOnly = true;
		edbutton.innerText = "Edit";
	}

}

