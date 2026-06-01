import socket
APP_VERSION = "v1.0.54"
_HOSTNAME = socket.gethostbyname(socket.gethostname())
UPDATE_URL = f"http://{_HOSTNAME}:8080/"
