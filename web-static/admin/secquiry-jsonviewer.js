var jsonViewer = new JSONViewer();
document.querySelector("#json_viewer").appendChild(jsonViewer.getContainer());
//document.querySelector("#view_json").appendChild(jsonViewer.getContainer());
function setJSON(jsonObj) {
	jsonViewer.showJSON(jsonObj);
};
