var modal = document.getElementById("myModal");
var closeButton = document.getElementsByClassName("closeButton")[0];
var saveList = document.getElementById("saveList");

var title = document.getElementById("projectTitle");
var crazyflieRuntimeState = "WAITING";

function openModal() {

    currCommand = SocketCommand.LIST_SAVES;
    ws.send(currCommand);

    saveList.innerHTML = "";
    var text = document.createElement("p");
    text.innerHTML = "<b>Loading...</b>";
    saveList.appendChild(text);

}
function closeModal() {
    modal.style.display="none";
}

closeButton.onclick = closeModal;
window.onclick = function(e) {

    if(e.target == modal) {
        closeModal();
    }
}

const SocketCommand = {
    SEND_CODE: "SEND_CODE",
    SAVE: "SAVE",
    LIST_SAVES: "LIST_SAVES",
    RESTORE_SAVE: "RESTORE_SAVE",
    RESTORE_LAST: "RESTORE_LAST",
    RESTORE_LAST_NAME: "RESTORE_LAST_NAME",
    SAVE_LAST: "SAVE_LAST",
};

var currCommand = null;
var ws = null;

if("WebSocket" in window) {
    ws = new WebSocket("ws://localhost:8001/test.py");
    ws.onopen = function() {
        document.getElementById("submit").disabled = false;
        document.getElementById("save").disabled = false;
        document.getElementById("restore").disabled = false;

        currCommand = SocketCommand.RESTORE_LAST_NAME;
        ws.send(currCommand);
    };
    ws.onmessage = function (evt) {
        var msg = evt.data;
        switch(currCommand) {
            case SocketCommand.LIST_SAVES:
                var files = msg.split("\n");
                saveList.innerHTML = "";
                modal.style.display = "block";
                for(i = 0; i< files.length; i++) {
                    var link = document.createElement("a");
                    link.title = files[i];
                    link.onclick = restore;
                    link.style.display = "block";
                    link.style.fontSize = "15px";
                    link.style.marginTop = "20px";
                    link.style.cursor = "pointer";
                    link.textContent = files[i];

                    var css = 'a:hover{ text-decoration: underline;color: blue }';
                    var style = document.createElement('style');
                    if (style.styleSheet)
                        style.styleSheet.cssText = css;
                    else
                        style.appendChild(document.createTextNode(css));
                    link.appendChild(style);
                    saveList.appendChild(link);
                }
                if(files.length == 1) {
                    var text = document.createElement("p");
                    text.innerHTML = "<b>No saved projects</b>";
                    saveList.appendChild(text);
                }
            break;
            case SocketCommand.RESTORE_SAVE:
                Blockly.mainWorkspace.clear();
                closeModal();
                if(msg != "\0") {
                    var xml = Blockly.Xml.textToDom(msg);
                    Blockly.Xml.domToWorkspace(xml, Blockly.mainWorkspace);
                }
            break;
            case SocketCommand.RESTORE_LAST_NAME:
                if(msg != "\0") {
                    title.textContent = msg;
                    ws.send(SocketCommand.RESTORE_LAST);
                    currCommand = SocketCommand.RESTORE_SAVE;
                }
            break;
        }
    };
    ws.onclose = function () {
        console.log("Connection Closed");
    }
} else {
    alert("WebSocket is not supported");
}

function saveLast() {
    if (!ws || ws.readyState !== WebSocket.OPEN)
        return;
    currCommand = SocketCommand.SAVE_LAST;
    ws.send(currCommand);
    ws.send(title.textContent);
}

function isCrazyflieWorkspace() {
    var topBlocks = workspace.getTopBlocks(true);
    return topBlocks.length === 1 && topBlocks[0].type.indexOf('webeeblocks_') === 0;
}

function submitCrazyflieMission() {
    if (!window.robotWindow || typeof window.robotWindow.send !== 'function')
        throw new Error('Crazyflie runtime transport is not ready');
    if (crazyflieRuntimeState === 'RUNNING')
        throw new Error('Crazyflie mission is already running');
    var message = WebeeBlocksCrazyflie.workspaceToMissionMessage(workspace);
    window.robotWindow.send(message);
}

function convertCode() {
    if (isCrazyflieWorkspace()) {
        try {
            submitCrazyflieMission();
        } catch (error) {
            console.error(error);
        }
        return;
    }

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.error('Historical Blockly sidecar is not connected');
        return;
    }
    currCommand = SocketCommand.SEND_CODE;
    var code = Blockly.Python.workspaceToCode(workspace);
    ws.send(SocketCommand.SEND_CODE);
    ws.send(code);
    saveLast();
}
function realTimeUpdate() {
    var code = Blockly.Python.workspaceToCode(workspace);
    document.getElementById('textCode').innerHTML = code;
}

function saveBlocks() {
    if (!ws || ws.readyState !== WebSocket.OPEN)
        return;
    currCommand = SocketCommand.SAVE;
    var xml = Blockly.Xml.workspaceToDom(Blockly.mainWorkspace);
    ws.send(SocketCommand.SAVE);
    ws.send(title.textContent+".xml");
    ws.send(Blockly.Xml.domToText(xml));
    saveLast();
}

function restore() {
    if (!ws || ws.readyState !== WebSocket.OPEN)
        return;
    currCommand = SocketCommand.RESTORE_SAVE;
    ws.send(currCommand);
    ws.send(this.innerText + ".xml");
    title.textContent = this.innerText;
}

function receiveMessage(value) {
    console.log(value);
    if (typeof value === 'string' && value.indexOf('WEBEEBLOCKS_MISSION_V1 ') === 0) {
        if (value === 'WEBEEBLOCKS_MISSION_V1 ACK')
            crazyflieRuntimeState = 'RUNNING';
        else if (value === 'WEBEEBLOCKS_MISSION_V1 DONE' || value.indexOf('WEBEEBLOCKS_MISSION_V1 ERR ') === 0)
            crazyflieRuntimeState = 'WAITING';
    }
    window.dispatchEvent(new CustomEvent('webeeblocks-wwi', {detail: value}));
}

function onResize(e) {
    Blockly.svgResize(workspace);
}

document.getElementById("submit").onclick = convertCode;
document.getElementById("save").onclick = saveBlocks;
document.getElementById("restore").onclick = openModal;

document.getElementById("submit").disabled = true;
document.getElementById("save").disabled = true;
document.getElementById("restore").disabled = true;

document.getElementById("projectTitle").addEventListener("keydown", (e) => {
    if(e.key === "Enter") e.preventDefault();
});

window.onload = async function() {
    const module = await import('https://cyberbotics.com/wwi/R2025a/RobotWindow.js');
    window.robotWindow = new module.default();
    window.robotWindow.receive = receiveMessage;
    // The Crazyflie runtime path does not require the historical WebSocket sidecar.
    document.getElementById("submit").disabled = false;
}

var container = document.getElementById("blocklyContainer");
