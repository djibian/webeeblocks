from controller import Robot

READY = "WEBEEBLOCKS_CI_WINDOW_READY"
CONTROLLER_TO_WINDOW = "WEBEEBLOCKS_CI_CONTROLLER_TO_WINDOW"
ACK = "WEBEEBLOCKS_CI_WINDOW_ACK"

robot = Robot()
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
            raise SystemExit(0)
        message = robot.wwiReceiveText()
