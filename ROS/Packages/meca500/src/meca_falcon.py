#!/usr/bin/env python

"""Connect to a Meca500 robot, activate and home it,
send a small program and then close the connection.
Usage:
    python RobotSampleProgram.py
"""
import rospy
import time
import sys
from threading import Timer
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Vector3

global robot
global x_direc
global y_direc
global z_direc
global Phi
global Theta
global Gamma
global grip
global is_close

x_direc = 0;
y_direc = 0;
z_direc = 0;
grip = 0;
is_close = 1;

ROBOT_IP = "192.168.0.100"   # IP of the robot
ROBOT_PORT = 10000           # Communication port

def callback(data):
    global x_direc
    global y_direc
    global z_direc
    global grip
    x_direc = data.axes[2]
    y_direc = data.axes[0] #Y direction
    z_direc = data.axes[1]
    grip = data.buttons[0]
	
def euler_callback(eu):
    global Phi
    global Theta
    global Gamma
    Phi = eu.x
    Theta = 2*(eu.y - 20) + 90  #Y direction
    Gamma = 2*(eu.z - 20)

def s_down():
    global robot
    sys.stdout.flush()
    print "Shutting down meca_falcon node"
    robot.run('ResetError')
    robot.run('Delay', [1])
    robot.run('DeactivateRobot')
    sys.stdout.flush()
    print("Closing connection")
    robot_disconnect()

def main_program():

    rospy.init_node('falcon_joy_teleop',anonymous=True)

    rospy.Subscriber("falcon/joystick", Joy, callback)
    rospy.Subscriber("euler_angles", Vector3, euler_callback)
    rate = rospy.Rate(10)

    """Main procedure"""
    global robot
    global x_direc
    global y_direc
    global z_direc
    global Phi
    global Theta
    global Gamma
    global grip
    global is_close

    Phi = 0
    Theta = 90
    Gamma = 0

    rospy.on_shutdown(s_down)

    robot_connect()
    print("Running program main_program...")
    sys.stdout.flush()

    # Set parameters
    robot.run('SetCartAngVel', [150])
    robot.run('SetCartLinVel', [200])
    robot.run('SetJointVel', [50])
    robot.run('SetCartAcc', [50])
    robot.run('SetJointAcc', [50])
    robot.run('SetBlending', [50])
    robot.run('SetAutoConf', [1])
    #robot.run('SetTRF', [65, 0, 19, 0, 90, 0])
    # Movements
    robot.run('MoveJoints', [-20.000, 10.000, -10.000, 20.000, -10.000, -10.000])
    robot.run('MoveJoints', [20.000, -10.000, 10.000, -20.000, 20.000, -10.000])
    robot.run('MoveJoints', [-20.000, 10.000, -10.000, 20.000, -10.000, -10.000])
    robot.run('MoveJoints', [0.000, -20.000, 20.000, 0.000, 20.000, 0.000])
    #robot.wait_for('3012', 'Did not receive EOB')
    robot.run('GetJoints')
    robot.get_response()
    robot.run('GripperOpen')
    is_close = 0
    #robot.run('Delay', [1])
    #robot.run('DeactivateRobot')
    #print("Main_program done")
    #sys.stdout.flush()
    robot.run('MovePose', [200, 0, 250, 0, 90, 0])
    #robot.wait_for('3012', 'Did not receive EOB')
    x_direc = 0.073;

    while not rospy.is_shutdown():
	#Regular mapped range
        x = 268 - (((x_direc - 0.073)/0.102)*80)
        y = (y_direc/0.055)*-208
        z = ((z_direc+0.057)/0.114)*220 + 70
	#z = ((z_direc+0.057)/0.112)*325 + 30

	#Constrined to a 3cm cube
	#x = 230 - (((x_direc - 0.073)/0.102)*0.5)
	#y = (y_direc/0.055)*-0.5 
	#z = ((z_direc+0.057)/0.112)*0.5 + 260

	if grip == 8:
	    if is_close:
	    	is_close = 0
	    	robot.run('GripperOpen')
		grip = 0
	    else:
		is_close = 1
		robot.run('GripperClose')
		grip = 0

        if Gamma > 40:
            Gamma = 40

        robot.run('MovePose', [x, y, z, Phi*4, Theta, Gamma])
        robot.wait_for('3012', 'Did not receive EOB')
	rate.sleep()

    robot.run('Delay', [1])
    #robot.run('DeactivateRobot')
    sys.stdout.flush()

def robot_connect():
    """Establish connection with the robot"""
    global robot
    robot = MecaRobot(ROBOT_IP, ROBOT_PORT)


def robot_disconnect():
    """Establish connection with the robot"""
    global robot
    robot.sock.close()


# ----------- communication class ------------- #
class MecaRobot:
    """Robot class for programming Meca500 robots"""
    def __init__(self, ip, port):
        import socket
        self.BUFFER_SIZE = 512  # bytes
        self.TIMEOUT = 60       # seconds
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.TIMEOUT)
        print('Connecting to robot %s:%i' % (ip, port))
        sys.stdout.flush()
        self.sock.connect((ip, port))

        # Receive welcome message
        print('Waiting for connection...')
        self.wait_for("3000", "Another user is already connected")

        # Reset, activate and home the robot
        self.run('ResetError')
        self.run('ActivateRobot')
        self.wait_for("2000", "Failed to activate the robot")
        self.run('Home')
        self.wait_for("2002", "Failed to home the robot")

    def send_str(self, msg):
        #Brayden
        #sent = self.sock.send(bytes(msg+'\0', 'ascii'))
        sent = self.sock.send(str(msg+'\0').encode('ascii'))
        if sent == 0:
            raise RuntimeError("Robot connection broken")

    def receive_str(self):
        byte_data = self.sock.recv(self.BUFFER_SIZE)
        if byte_data == b'':
            raise RuntimeError("Robot connection broken")
        return byte_data.decode('ascii')

    def run(self, cmd, values=None):
        if isinstance(values, list):
            str_send = cmd + '(' + (','.join(format(vi, ".6f") for vi in values)) + ')'
        elif values is None:
            str_send = cmd
        else:
            str_send = cmd + '(' + str(values) + ')'

        # Send command to robot
        self.send_str(str_send)

        print('Running: ' + str_send)
        sys.stdout.flush()

    def get_response(self):
        robot_answer = ""
        while robot_answer == "":
            robot_answer = self.receive_str()

        print('Received: %s' % robot_answer)
        sys.stdout.flush()

    def wait_for(self, answer, error_message):
        answer_timer = Timer(10, self.answer_not_found, args=error_message)
        robot_answer = ""

        # loop to find answer, if answer is not found after 10 seconds print error message
        while robot_answer != answer:
            robot_output = self.receive_str()

            if robot_output.find(answer) == -1 & answer_timer.is_alive() is False:
                answer_timer.start()
                answer_timer.join()

            elif robot_output.find(answer) != -1:
                robot_answer = answer

        answer_timer.cancel()
        print('Received: %s' % robot_answer)
        sys.stdout.flush()

    @staticmethod
    def answer_not_found(error_message):
        print(error_message)
        exit(0)


if __name__ == "__main__":
    """Call Main procedure"""
    main_program()
    time.sleep(8)
    print("Closing connection")
    #robot_disconnect()

    # Pause execution before closing process (allows users to read last message)
    time.sleep(2)
