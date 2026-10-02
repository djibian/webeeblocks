from pathlib import Path

from controller import Supervisor

READY = "WEBEEBLOCKS_CI_WINDOW_READY"
CONTROLLER_TO_WINDOW = "WEBEEBLOCKS_CI_CONTROLLER_TO_WINDOW"
ACK = "WEBEEBLOCKS_CI_WINDOW_ACK"
PROOF = (
    Path(__file__).resolve().parents[2]
    / "ci-artifacts"
    / "robot-window-roundtrip-proof.txt"
)

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())
print("WEBEEBLOCKS_CI_ROBOT_WINDOW_CONTROLLER_STARTED", flush=True)

while robot.step(timestep) != -1:
    message = robot.wwiReceiveText()
    while message:
        print(f"WEBEEBLOCKS_CI_WWI_RX={message}", flush=True)
        if message == READY:
            print("WEBEEBLOCKS_CI_WINDOW_TO_CONTROLLER_OK", flush=True)
            robot.wwiSendText(CONTROLLER_TO_WINDOW)
            print("WEBEEBLOCKS_CI_CONTROLLER_TO_WINDOW_SENT", flush=True)
        elif message == ACK:
            print("WEBEEBLOCKS_CI_ROBOT_WINDOW_ROUNDTRIP_OK", flush=True)
            # The ACK is the functional proof. Persist it in the bind-mounted
            # workspace before requesting Webots shutdown so acceptance does not
            # depend on asynchronous controller stdout forwarding during exit.
            PROOF.parent.mkdir(parents=True, exist_ok=True)
            temp_proof = PROOF.with_suffix(".tmp")
            temp_proof.write_text(
                "WEBEEBLOCKS_CI_WWI_RX=WEBEEBLOCKS_CI_WINDOW_ACK\n"
                "WEBEEBLOCKS_CI_ROBOT_WINDOW_ROUNDTRIP_OK\n",
                encoding="utf-8",
            )
            temp_proof.replace(PROOF)
            robot.simulationQuit(0)
            raise SystemExit(0)
        message = robot.wwiReceiveText()
