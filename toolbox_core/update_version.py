import socket
APP_VERSION = "v1.0.3"
_HOSTNAME = socket.gethostname()
UPDATE_URL = f"http://{_HOSTNAME}:8080/update/"
