from functools import wraps
import random
import re

from flask import Flask, current_app, jsonify, request
import requests


app = Flask(__name__)


# TODO: configuration handling
app.config["hs_token"] = "b3b05236568ab46f0d98a978936c514eac93d8f90e6d5cd3895b3db5bb8d788b"
app.config["as_token"] = "a2d7789eedb3c5076af0864f4af7bef77b1f250ac4e454c373c806876e939cca"
app.config["homeserver"] = "http://synapse:8008"
app.config["user_id"] = "@_cactusbot:localhost:8008"
app.config["namespace_regex"] = "#_comments_.*"
# We assume that we own a prefix
# TODO validate on startup that the appservice will work with the assigned
# namespace
app.config["namespace"] = "_comments_"


HELP_MSG = """\
🌵 Hi I'm here to help you with Cactus Comments (https://cactus.chat) 🌵

To get started, register a namespace by typing:

    register <namespace>

Where <namespace> is replaced by any name you like. The namespace ensures that\
 you are moderator in your comment sections 👮‍♀️

After you have registered a namespace, go to \
https://cactus.chat/docs/getting-started to learn how to embed comment sections
wherever you like!

You can read more about moderation here: https://cactus.chat/docs/moderation
"""

MODERATION_EXPLANATION = """\
Hi there! You just registered a Cactus Comments namespace 🌵

* insert brief explanation here and possible commands *
"""


def send_plaintext_msg(room_id, msg):
    txn_id = random.randint(0, 1_000_000_000)
    return requests.put(
        current_app.config["homeserver"]
        + f"/_matrix/client/r0/rooms/{room_id}/send/m.room.message/{txn_id}",
        params={"access_token": current_app.config["as_token"]},
        json={"msgtype": "m.text", "body": msg},
    )


def _in_our_namespace(room_state_list):
    """Return `True` if the room is in our namespace."""
    for state in room_state_list:
        if state["type"] != "m.room.canonical_alias":
            continue
        alias = state["content"]["alias"]
        namespace_regex = current_app.config["namespace_regex"]
        if re.match(namespace_regex, alias) is not None:
            return True
    return False


def authorization_required(f):
    """Make sure that the homeserver passed the correct hs_token.

    Respond with M_FORBIDDEN, if the token does not match.

    Usage:
        @authorization_required
        def my_func_that_requires_authorization():
            ...
    """

    @wraps(f)
    def inner(*args, **kwargs):
        token = request.args.get("access_token", False)
        hs_token = current_app.config["hs_token"]
        if not token:
            return jsonify({"errcode": "CHAT.CACTUS.APPSERVICE_UNAUTHORIZED"}), 401
        if token != hs_token:
            return jsonify({"errcode": "CHAT.CACTUS.APPSERVICE_FORBIDDEN"}), 403
        return f(*args, **kwargs)

    return inner


@app.route("/transactions/<string:txn_id>", methods=["PUT"])  # deprecated
@app.route("/_matrix/app/v1/transactions/<string:txn_id>", methods=["PUT"])
@authorization_required
def new_transaction(txn_id: str):
    """Implement the Push API from the appservice specification.

    The homeserver hits this endpoint to notify us of new events in our rooms.

    Reference: https://matrix.org/docs/spec/application_service/r0.1.2#put-matrix-app-v1-transactions-txnid
    """

    events = request.get_json()["events"]

    for event in events:
        room_id = event["room_id"]
        if event["type"] == "m.room.member":
            is_invite = event["content"]["membership"] == "invite"
            is_for_me = event["state_key"] == current_app.config["user_id"]
            if is_invite and is_for_me:
                # Accept invite / join room
                r = requests.post(
                    current_app.config["homeserver"]
                    + f"/_matrix/client/r0/rooms/{room_id}/join",
                    params={"access_token": current_app.config["as_token"]},
                    json={},
                )

        if event["type"] == "m.room.message":
            if event["content"]["msgtype"] != "m.text":
                continue
            msg = event["content"]["body"]
            if not (msg == "help" or msg.startswith("register")):
                # Only react to "help" and "register <namespace>" messages
                continue

            # Make sure we don't respond to comments
            r = requests.get(
                current_app.config["homeserver"]
                + f"/_matrix/client/r0/rooms/{room_id}/state",
                params={"access_token": current_app.config["as_token"]},
            )
            if _in_our_namespace(r.json()):
                continue

            if msg == "help":
                send_plaintext_msg(room_id, HELP_MSG)
                continue

            namespace = msg.split(" ")[1]
            # TODO Check for other invalid room alias names, e.g. length and
            # invalid chars.
            if "_" in namespace:
                error_msg = 'Sorry, underscore ("_") is not allowed in namespace names'
                send_plaintext_msg(room_id, error_msg)
                continue

            # Try to create, will fail if already exists
            r = requests.post(
                current_app.config["homeserver"] + "/_matrix/client/r0/createRoom",
                params={"access_token": current_app.config["as_token"]},
                json={
                    "visibility": "private",
                    "room_alias_name": current_app.config["namespace"] + namespace,
                    "name": f"{namespace} moderation room",
                    "topic": f"Moderation room for {namespace}. For more, visit https://cactus.chat",
                    "invite": [event["sender"]],
                    "creation_content": {"m.federate": True},
                    "initial_state": [
                        # Make the room invite only.
                        {
                            "type": "m.room.join_rules",
                            "content": {"join_rule": "invite"},
                        },
                        # Make future room history visible to members since
                        # they were invited.
                        {
                            "type": "m.room.history_visibility",
                            "content": {"history_visibility": "invited"},
                        },
                    ],
                    # Make sender admin in new room
                    "power_level_content_override": {
                        "users": {
                            event["sender"]: 100,
                            current_app.config["user_id"]: 100,
                        }
                    },
                },
            )
            rjson = r.json()

            if not r.ok:
                errcode = rjson.get("errcode", "")
                if errcode == "M_ROOM_IN_USE":
                    msg = f"Sorry, {namespace} is already used by someone else."
                    send_plaintext_msg(room_id, msg)
                    continue
                else:
                    error_msg = rjson.get("error", "no error message")
                    msg = f"Unknown error. Error from homeserver: {error_msg}."
                    send_plaintext_msg(room_id, msg)
                    continue

            send_plaintext_msg(room_id, f"Created namespace {namespace} for you 🚀")
            send_plaintext_msg(rjson["room_id"], MODERATION_EXPLANATION)

    return jsonify({}), 200


@app.route("/rooms/<path:alias>", methods=["GET"])  # deprecated
@app.route("/_matrix/app/v1/rooms/<path:alias>", methods=["GET"])
@authorization_required
def query_room_alias(alias: str):
    """Implement the Room Alias Query API from the appservice specification.

    The homeserver hits this endpoint to see if a room alias exists. We are
    only queried for rooms in our alias namespace. In our namespace, all rooms
    exist. Therefore, we MUST create the room before responding.

    Reference: https://matrix.org/docs/spec/application_service/r0.1.2#get-matrix-app-v1-rooms-roomalias
    """

    alias_localpart = alias.split(":")[0][1:]

    # There has to be exactly one more underscore in alias_localpart, than in
    # the appservice namespace. Otherwise, the user is trying to join a
    # moderation room or create a room with an invalid alias.
    if current_app.config["namespace"].count("_") + 1 != alias_localpart.count("_"):
        return jsonify({
            "errcode": "CHAT.CACTUS.APPSERVICE_NOT_FOUND",
        }), 404

    # Create room
    r = requests.post(
        current_app.config["homeserver"] + "/_matrix/client/r0/createRoom",
        params={"access_token": current_app.config["as_token"]},
        json={
            "visibility": "private",
            "room_alias_name": alias_localpart,
            "creation_content": {"m.federate": True},
            "initial_state": [
                # Make the room public to whoever knows the link.
                {
                    "type": "m.room.join_rules",
                    "content": {"join_rule": "public"},
                },
                # Allow guests to join the room.
                {
                    "type": "m.room.guest_access",
                    "content": {"guest_access": "can_join"},
                },
                # Make future room history visible to anyone.
                {
                    "type": "m.room.history_visibility",
                    "content": {"history_visibility": "world_readable"},
                },
            ],
        },
    )

    if not r.ok:
        if r.json().get("errcode") == "M_ROOM_IN_USE":
            # Room already exists!
            return jsonify({}), 200

        # This can fail for a few reasons: if we messed up the request, created
        # a room in an invalid state, or the room version is unsupported by the
        # homeserver. Regardless, the room does not exist.
        homeserver_err_msg = r.json().get("error", "no error message")
        return jsonify({
            "errcode": "CHAT.CACTUS.APPSERVICE_NOT_FOUND",
            "error": "Unknown error. Error from homeserver: {homeserver_err_msg}.",
        }), 404

    # 200, with an empty json object indicates that the room exists.
    return jsonify({}), 200
