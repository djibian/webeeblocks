var modal = document.getElementById("myModal");
var closeButton = document.getElementsByClassName("closeButton")[0];
var saveList = document.getElementById("saveList");

var title = document.getElementById("projectTitle");
var crazyflieRuntimeState = "WAITING";
var webeeblocksChallengeState = "READY";
var blocklyDomainEditSeen = false;

function ensureChallengePanel() {
    var panel = document.getElementById('webeeblocksChallenge');
    if (panel)
        return panel;
    panel = document.createElement('div');
    panel.id = 'webeeblocksChallenge';
    panel.style.display = 'flex';
    panel.style.gap = '18px';
    panel.style.alignItems = 'center';
    panel.style.padding = '8px 12px';
    panel.style.margin = '4px 0 8px 0';
    panel.style.border = '1px solid #bbb';
    panel.style.borderRadius = '6px';
    panel.style.fontFamily = 'sans-serif';
    panel.innerHTML = '<strong>Défi</strong>' +
        '<span>État : <b id="webeeblocksChallengeState">PRÊT</b></span>' +
        '<span>Résultat : <b id="webeeblocksChallengeResult">—</b></span>' +
        '<span>Temps : <b id="webeeblocksChallengeTime">—</b></span>';
    var container = document.getElementById('blocklyContainer');
    if (container && container.parentNode)
        container.parentNode.insertBefore(panel, container);
    return panel;
}

function setChallengeDisplay(state, result, elapsed) {
    ensureChallengePanel();
    webeeblocksChallengeState = state;
    var stateNode = document.getElementById('webeeblocksChallengeState');
    var resultNode = document.getElementById('webeeblocksChallengeResult');
    var timeNode = document.getElementById('webeeblocksChallengeTime');
    if (stateNode)
        stateNode.textContent = state === 'RUNNING' ? 'EN VOL' : (state === 'FINISHED' ? 'TERMINÉ' : 'PRÊT');
    if (resultNode)
        resultNode.textContent = result || '—';
    if (timeNode)
        timeNode.textContent = elapsed === null || elapsed === undefined ? '—' : Number(elapsed).toFixed(2) + ' s';
    window.dispatchEvent(new CustomEvent('webeeblocks-challenge', {
        detail: {state: state, result: result || null, elapsed: elapsed === undefined ? null : elapsed}
    }));
}

function challengeResultLabel(status) {
    if (status === 'SUCCESS') return 'RÉUSSI';
    if (status === 'COLLISION') return 'COLLISION';
    if (status === 'GATE_MISSED') return 'PASSAGE MANQUÉ';
    return status;
}

function handleChallengeMessage(value) {
    if (typeof value !== 'string' || value.indexOf('WEBEEBLOCKS_CHALLENGE_V1 ') !== 0)
        return false;
    if (value === 'WEBEEBLOCKS_CHALLENGE_V1 START') {
        setChallengeDisplay('RUNNING', null, 0);
        return true;
    }
    var tick = value.match(/^WEBEEBLOCKS_CHALLENGE_V1 TICK elapsed=([0-9]+(?:\.[0-9]+)?)$/);
    if (tick) {
        if (webeeblocksChallengeState === 'RUNNING')
            setChallengeDisplay('RUNNING', null, Number(tick[1]));
        return true;
    }
    var result = value.match(/^WEBEEBLOCKS_CHALLENGE_V1 RESULT (SUCCESS|COLLISION|GATE_MISSED) elapsed=([0-9]+(?:\.[0-9]+)?)$/);
    if (result) {
        setChallengeDisplay('FINISHED', challengeResultLabel(result[1]), Number(result[2]));
        return true;
    }
    return true;
}

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
    if (crazyflieRuntimeState !== 'WAITING')
        throw new Error('Crazyflie mission is already pending, running, or recovering');
    var message = WebeeBlocksCrazyflie.workspaceToMissionMessage(workspace);
    crazyflieRuntimeState = 'PENDING';
    blocklyDomainEditSeen = false;
    try {
        window.robotWindow.send(message);
    } catch (error) {
        crazyflieRuntimeState = 'WAITING';
        throw error;
    }
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
    // Crazyflie blocks deliberately have no Python generator: the student-facing
    // runtime path serializes semantic missions over WWI instead. Keep the
    // historical Python preview untouched for non-Crazyflie workspaces only.
    if (isCrazyflieWorkspace()) {
        document.getElementById('textCode').innerHTML = '';
        return;
    }
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
    if (handleChallengeMessage(value)) {
        window.dispatchEvent(new CustomEvent('webeeblocks-wwi', {detail: value}));
        return;
    }
    var acknowledgeDone = false;
    if (typeof value === 'string' && value.indexOf('WEBEEBLOCKS_MISSION_V1 ') === 0) {
        if (value === 'WEBEEBLOCKS_MISSION_V1 ACK') {
            if (crazyflieRuntimeState === 'PENDING')
                crazyflieRuntimeState = 'RUNNING';
        } else if (value === 'WEBEEBLOCKS_MISSION_V1 DONE') {
            // DONE means the mission is terminal, but the vehicle is not yet
            // guaranteed to have completed its physical reset/rearm sequence.
            crazyflieRuntimeState = 'RECOVERING';
            acknowledgeDone = true;
        } else if (value === 'WEBEEBLOCKS_MISSION_V1 RUNTIME_READY') {
            if (crazyflieRuntimeState === 'RECOVERING') {
                crazyflieRuntimeState = 'WAITING';
                if (blocklyDomainEditSeen && webeeblocksChallengeState === 'FINISHED')
                    setChallengeDisplay('READY', null, null);
            }
        } else if (value.indexOf('WEBEEBLOCKS_MISSION_V1 ERR ') === 0) {
            // BUSY can be the response to a second transport-level probe while an
            // already accepted mission is still active. Never let it unlock Submit.
            if (value !== 'WEBEEBLOCKS_MISSION_V1 ERR BUSY' && crazyflieRuntimeState === 'PENDING')
                crazyflieRuntimeState = 'WAITING';
        }
    }
    window.dispatchEvent(new CustomEvent('webeeblocks-wwi', {detail: value}));
    if (acknowledgeDone && window.robotWindow && typeof window.robotWindow.send === 'function') {
        window.robotWindow.send('WEBEEBLOCKS_MISSION_V1 DONE_ACK');
        window.dispatchEvent(new CustomEvent('webeeblocks-runtime', {detail: 'DONE_ACK_SENT'}));
    }
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
    ensureChallengePanel();
    setChallengeDisplay('READY', null, null);
    const module = await import('https://cyberbotics.com/wwi/R2025a/RobotWindow.js');
    window.robotWindow = new module.default();
    window.robotWindow.receive = receiveMessage;
    // The Crazyflie runtime path does not require the historical WebSocket sidecar.
    document.getElementById("submit").disabled = false;
}

var container = document.getElementById("blocklyContainer");
var workspace = Blockly.inject(container,
    {
        toolbox: document.getElementById('toolbox'),
        scrollbars: true,
        media: 'google-blockly-31ee4ea/media/'
    });
Blockly.svgResize(workspace);
workspace.addChangeListener(realTimeUpdate);
workspace.addChangeListener(function(event) {
    if (!event || event.type === Blockly.Events.UI)
        return;
    // A FINISHED challenge can only have been produced by the Crazyflie runtime.
    // Treat any genuine non-UI workspace edit as a student retry intent; checking
    // the whole workspace shape here is brittle during Blockly's change dispatch.
    if (webeeblocksChallengeState === 'FINISHED' &&
        (crazyflieRuntimeState === 'WAITING' || crazyflieRuntimeState === 'RECOVERING')) {
        blocklyDomainEditSeen = true;
        setChallengeDisplay('READY', null, null);
    }
});
