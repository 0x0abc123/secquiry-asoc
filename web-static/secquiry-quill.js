// Quill editor --------------------------------------------------------------------------------------------------------

var toolbarOptions = [
  ['bold', 'italic', 'underline', 'strike'],        // toggled buttons
  ['blockquote', 'code-block'],

  [{ 'header': 1 }, { 'header': 2 }],               // custom button values
  [{ 'list': 'ordered'}, { 'list': 'bullet' }],
  [{ 'script': 'sub'}, { 'script': 'super' }],      // superscript/subscript
  [{ 'indent': '-1'}, { 'indent': '+1' }],          // outdent/indent
  [{ 'direction': 'rtl' }],                         // text direction

  [{ 'size': ['small', false, 'large', 'huge'] }],  // custom dropdown
  [{ 'header': [1, 2, 3, 4, 5, 6, false] }],

  [{ 'color': [] }, { 'background': [] }],          // dropdown with defaults from theme
  [{ 'font': [] }],
  [{ 'align': [] }],
  ['image'],
  ['video'],
  ['clean']                                         // remove formatting button
];

var quill = new Quill('#editor', {
  modules: {
    toolbar: toolbarOptions
  },
  theme: 'snow'
});
quill.disable();

//Instead of this maybe use: event.dataTransfer.setData and getData?
var quillGlobal = { CurrentUid: '' };

function toggleQuill()
{
	let isEnabled = quill.isEnabled();
	if(isEnabled)
		_panesIndex['edit']['editor'].onAfterSubmit();
	else
		v_action_funcs['edit'](quillGlobal.CurrentUid);
}

function populateQuill(nodeinfo)
{
	// serializedDelta can be stored in persistent storage or sent in a message etc.
	let serialisedDeltas = nodeinfo[PROP_TEXTDATA] ||  "{}";
	quill.setContents(JSON.parse(serialisedDeltas));	
	let edtitle = document.getElementById('editor_title');
	edtitle.value = nodeinfo[PROP_LABEL];
}

function getQuillEdits(nodeinfo)
{
	let edtitle = document.getElementById('editor_title');
	let deltas = quill.getContents();
	nodeinfo[PROP_TEXTDATA] = JSON.stringify(deltas);
	nodeinfo[PROP_LABEL] = edtitle.value;
	nodeinfo[PROP_DETAIL] = 'Note';
}

function setQuillVisualState(status)
{
	let edbutton = document.getElementById('toggleEditing');
	let edtitle = document.getElementById('editor_title');

	if(status == 'enable') {
		quill.enable();
		edtitle.readOnly = false;
		edbutton.innerText = "Save";
	}
	else {
		quill.disable();
		edtitle.readOnly = true;
		edbutton.innerText = "Edit";
	}

}

