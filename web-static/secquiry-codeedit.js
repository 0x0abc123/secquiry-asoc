// Code editor --------------------------------------------------------------------------------------------------------

//Instead of this maybe use: event.dataTransfer.setData and getData?
var codeEditGlobal = { CurrentUid: '' };

var isCodeEditEnabled = false;

function toggleCodeEdit()
{
	if(isCodeEditEnabled)
		_panesIndex['edit']['codeedit'].onAfterSubmit();
	else
		v_action_funcs['edit'](codeEditGlobal.CurrentUid);
}

_ce_ids_to_commentidx = {};
_cecomments = [];

function setCodeEditVisualState(status)
{
	let edbutton = document.getElementById('toggleCodeEdit');

	if(status == 'enable') {
		edbutton.innerText = "Save";
	}
	else {
		edbutton.innerText = "Edit";
	}
	isCodeEditEnabled = (status == 'enable');
}

function getCodeEdits(nodeinfo)
{
	let commentsToSerialize = [];
	_cecomments.forEach(c => { if (c["n"] > 0) commentsToSerialize.push(c) });
	let serializedComments = JSON.stringify(commentsToSerialize);
	let startOfActualCode = nodeinfo[PROP_TEXTDATA].indexOf("\n");
	let updatedData = serializedComments+nodeinfo[PROP_TEXTDATA].substring(startOfActualCode);
	nodeinfo[PROP_TEXTDATA] = updatedData;
}

function getCommentObjectForId(comment_id) {
	return _cecomments[_ce_ids_to_commentidx[comment_id]];
}

function renderCommentText(text) {
	return ' ▼ '+text
}

//comment object should be created and added to _cecomments before calling this function
function insertCommentRow(beforeElement, comment_index=0) {
	let c = _cecomments[comment_index];
	//create random ID in here and set it as custom attribute on row
	let c_id = c["t"].toString(36)+c["n"];
	//store the random ID in the global randID->commentID map
	_ce_ids_to_commentidx[c_id] = comment_index;
	var dtr = document.createElement('tr');
	var dtrLineNum = document.createElement('td')
	var dtrText = document.createElement('td')
	var dtrTextPre = document.createElement('pre')
	var dtrTextCode = document.createElement('code')
	dtrText.setAttribute('class', "cecomment");
	dtrTextCode.setAttribute('c_id', c_id);
	dtrTextPre.appendChild(dtrTextCode);
	dtrText.appendChild(dtrTextPre);
	dtrLineNum.setAttribute('class', 'cecomment');
	let text = c["c"];
	dtrTextCode.textContent = renderCommentText(text);	
	dtr.appendChild(dtrLineNum);
	dtr.appendChild(dtrText);
	beforeElement.parentNode.insertBefore(dtr,beforeElement);
}

function codeedit_clickcancel() {
	let pu = document.getElementById('codeedit_popup');
	pu.style.display = 'none';
}

function codeedit_clickdel() {
	let pu = document.getElementById('codeedit_popup');
	pu.style.display = 'none';
	let c_id = pu.getAttribute('c_id');
	if(c_id) {
		let co = getCommentObjectForId(c_id);
		co["c"] = "";
		co["n"] = -1;
		let target = document.querySelector('[c_id="'+c_id+'"]');
		target.parentNode.parentNode.parentNode.remove();
	}
}

function codeedit_clickOK() {
	console.log('buttonclickOK');
	let pu = document.getElementById('codeedit_popup');
	let pu_input = document.getElementById('codeedit_popup_input');
	pu.style.display = 'none';
	let c_id = pu.getAttribute('c_id');
	let ln = pu.getAttribute('ln') || 1;
	let commentText = pu_input.value;
	
	//editing existing comment
	if(c_id) {
		getCommentObjectForId(c_id)["c"] = commentText;
		let target = document.querySelector('[c_id="'+c_id+'"]');
		target.textContent = renderCommentText(commentText);
	}
	//adding new comment
	else {
		let totalcomments = _cecomments.push({'t':Date.now(),'n':parseInt(ln),'c':commentText});
		let target = document.querySelector('[data-line-number="'+ln+'"]');
		let clickedRow = target.parentNode;
		insertCommentRow(clickedRow, totalcomments-1);
	}
}

function showEditPopup(target,addCommentToLineNum=0) {
	//console.log('clicked cecomment');
	//let c_id = target.getAttribute('c_id');
	let elrec = target.getBoundingClientRect();
	//console.log(target);
	//console.log(elrec.top, elrec.right, elrec.bottom, elrec.left);
	let pu = document.getElementById('codeedit_popup');
	pu.setAttribute('ln',addCommentToLineNum);
	
	if(addCommentToLineNum == 0)
		pu.setAttribute('c_id',target.getAttribute('c_id'));
	else
		pu.removeAttribute('c_id');
	
	let pu_input = document.getElementById('codeedit_popup_input');
	pu_input.value = (addCommentToLineNum > 0) ? '' : target.textContent.substring(3);
	pu.style.position = 'absolute';
	pu.style.top = elrec.top > 60 ? (elrec.top-60)+"px" : "0px";
	pu.style.left = elrec.left+"px";
	pu.style.width = "60%";
	pu_input.style.width = "100%";
	pu_input.style.height = "2.5em";
	pu.style.display = 'block';
	//document.getElementById('popuptest').style.position = 'absolute';
}

function handleComment(e) {
	if(!isCodeEditEnabled)
		return;
    var target = e.target || e.srcElement;
	var tableRowElement = target.parentNode;
	var targetClass = target.className ;
	if(targetClass == 'hljs-ln-n')
	{
		//console.log(target);
		var lineNum = target.getAttribute("data-line-number");
		var ln = 0;
		if (!(parseInt(lineNum) > 0))
			return;
		else
			ln = parseInt(lineNum);
		//console.log(lineNum);
		
		showEditPopup(target, ln);
		/*
		var commentText = prompt('enter comment: ');
		if (!commentText)
			return;
		var commentLine = {'t':Date.now(),'n':ln,'c':commentText};
		let totalcomments = _cecomments.push(commentLine);

		let clickedRow = target.parentNode.parentNode;
		insertCommentRow(clickedRow, totalcomments-1);
		*/
	}
	else if (target.getAttribute('c_id'))
	{
		showEditPopup(target);		
	}
}

async function renderCode(rawstr, language) {
	var inputcodearr = rawstr.split("\n");
	//the first line is a serialized JSON object containing the saved comments
	_cecomments = JSON.parse(inputcodearr[0]);
	//skip inputcodearr[0], which is the comment metadata
	let codetext = inputcodearr.slice(1).join("\n");
	let dtcode = document.getElementById('codeedit_code');
	dtcode.textContent = codetext;//escapeCode(codetext);
	dtcode.setAttribute("class","language-"+language);
	hljs.highlightElement(dtcode);
	hljs.initLineNumbersOnLoad();
}

async function populateCodeEdit(nodeinfo) {
	
	_ce_ids_to_commentidx = {};

	var dtjsdiv = document.getElementById('codeedit_js');
	dtjsdiv.innerHTML = null;
	
	let fileExt = nodeinfo[PROP_LABEL].split('.').pop(); 
	let nodeLanguage = fileExt ? ce_lang_table[fileExt] : '';
	if (!nodeLanguage)
		nodeLanguage = "plaintext";
	let hljsLangScript = document.createElement("script");
	hljsLangScript.setAttribute("src", "hljs/languages/"+nodeLanguage+".min.js");
	dtjsdiv.appendChild(hljsLangScript);
		
	let counter = 0;
	while(!hljs.getLanguage(nodeLanguage) && (counter++ < 10)){
		await new Promise(r => setTimeout(r, 300));	
	}
	
	var inputcode = nodeinfo[PROP_TEXTDATA] ||  "{}";
	await renderCode(inputcode, nodeLanguage);
	
	commentsInitialised = false;
	mutationObserver = new MutationObserver(function(mutations) {
	  mutations.forEach(function(mutation) {
		if(!commentsInitialised){
			commentsInitialised = initComments(mutationObserver);
		}
	  });
	});

	dyntable = document.getElementById('codeedit');
	mutationObserver.observe(dyntable, {
	  childList: true,
	  subtree: true,
	});

}

var dyntable = document.getElementById('codeedit');
dyntable.addEventListener("click", handleComment);

var commentsInitialised = false;
var mutationObserver = null;

function initComments(observer)
{
	var lnumbers = document.querySelectorAll('.hljs-ln-numbers');
	if (!lnumbers || lnumbers.length < 1)
		return false;
	observer.disconnect();
	let mapLineNumsToElements = {};
	lnumbers.forEach( el => {
		let ln = el.getAttribute("data-line-number");
		mapLineNumsToElements[ln] = el;
	} );
	_cecomments.forEach( (c,i) => {
		console.log("n: "+c["n"]+", c: "+c["c"]);
		let beforeElement = mapLineNumsToElements[c["n"]];
		if(beforeElement)
			insertCommentRow(beforeElement.parentNode, i);
	});
	return true;
}



var ce_lang_table = {
"js":"javascript",
"json":"javascript",
"asp":"vbscript-html",
"aspx":"csharp-html",
"asmx":"csharp-html",
"ascx":"csharp-html",
"asax":"csharp-html",
"axd":"csharp-html",
"xml":"xml",
"xsd":"xml",
"dtd":"xml",
"xslt":"xml",
"xsl":"xml",
"html":"xml",
"html5":"xml",
"rss":"xml",
"htm":"xml",
"resx":"xml",
"csproj":"xml",
"config":"xml",
"wsdl":"xml",
"xaml":"xml",
"s":"x86asm",
"asm":"x86asm",
"sln":"properties",
"plist":"properties",
"properties":"properties",
"md":"markdown",
"php":"php",
"inc":"php",
"php3":"php",
"php5":"php",
"php7":"php",
"phtml":"php",
"phtm":"php",
"css":"css",
"c":"c",
"h":"c",
"cc":"cpp",
"cpp":"cpp",
"hpp":"cpp",
"py":"python",
"rpy":"python",
"p":"python",
"sh":"bash",
"run":"bash",
"bat":"dos",
"r":"r",
"rb":"ruby",
"irb":"ruby",
"cs":"csharp",
"fs":"fsharp",
"lua":"lua",
"m":"objectivec",
"pl":"perl",
"pm":"perl",
"vbscript":"vbscript",
"vbs":"vbscript",
"vb":"vbscript",
"vba":"vbscript",
"gradle":"gradle",
"go":"go",
"yaml":"yaml",
"smali":"smali",
"java":"java",
"jsp":"java-html",
"swift":"swift",
"sql":"sql",
"cmake":"cmake",
"makefile":"makefile",
"make":"makefile",
"kt":"kotlin",
"kts":"kotlin",
"ps1":"powershell",
"psm":"powershell",
"psd":"powershell",
"psm1":"powershell",
"psd1":"powershell",
"au3":"autoit",
"ada":"ada",
"scala":"scala",
"rs":"rust",
"dockerfile":"dockerfile",
"ts":"typescript",
"txt":"plaintext"
}