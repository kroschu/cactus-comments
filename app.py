from functools import wraps

from flask import Flask, current_app, jsonify, request
import requests


app = Flask(__name__)


# TODO: configuration handling
app.config["hs_token"] = "b3b05236568ab46f0d98a978936c514eac93d8f90e6d5cd3895b3db5bb8d788b"
app.config["as_token"] = "a2d7789eedb3c5076af0864f4af7bef77b1f250ac4e454c373c806876e939cca"
app.config["homeserver"] = "http://synapse:8008"
app.config["user_id"] = "@_cactusbot:localhost:8008"


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
        if event["type"] == "m.room.member":
            is_invite = event["content"]["membership"] == "invite"
            is_for_me = event["state_key"] == current_app.config["user_id"]
            if is_invite and is_for_me:
                room_id = event["room_id"]
                # Accept invite / join room
                r = requests.post(
                    current_app.config["homeserver"] + f"/_matrix/client/r0/rooms/{room_id}/join",
                    params={"access_token": current_app.config["as_token"]},
                    json={},
                )

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

    # Create room
    alias_localpart = alias.split(":")[0][1:]
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
        # This should never happend. We indicate 404 - that the room does not
        # exist - and an appropriate error message.
        homeserver_err_msg = r.json().get("error", "no error message")
        return jsonify({
            "errcode": "CHAT.CACTUS.APPSERVICE_NOT_FOUND",
            "error": "Unknown error. Error from homeserver: {homeserver_err_msg}.",
        }), 404

    # 200, with an empty json object indicates that the room exists.
    return jsonify({}), 200
