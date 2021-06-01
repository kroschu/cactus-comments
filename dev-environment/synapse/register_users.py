import requests
import time


def register(username):
    """ Ensure that `username` is registered.
        Terminates on successful register, or if user is already registered.
        Retries on connection error. Useful while synapse is starting.
    """
    print(f"🔧 Registering user: {username}")
    while True:
        try:
            r = requests.post(
                "http://localhost:8008/_matrix/client/r0/register",
                json={
                    "auth": {"type": "m.login.dummy"},
                    "username": username,
                    "password": username
                }
            )
            if r.status_code == 200:
                print(f"🔧 Successfully registered user: {username}")
                return
            if r.status_code == 400 and r.json()["errcode"] == "M_USER_IN_USE":
                print(f"🔧 User already registered: {username}")
                return
            else:
                print(f"🔧 Bad status when registering: {r.status_code}, {r.text}")
        except Exception as e:
            print(f"🔧 Error registering: {e}")
        time.sleep(2)


register("dev1")
register("dev2")
register("dev3")
