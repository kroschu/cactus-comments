from functools import wraps

from flask import Flask, jsonify, request


app = Flask(__name__)


# TODO: configuration handling
app.config["hs_token"] = "b3b05236568ab46f0d98a978936c514eac93d8f90e6d5cd3895b3db5bb8d788b"


def authorization_required(app):
    """Make sure that the homeserver passed the correct hs_token.

    Respond with M_FORBIDDEN, if the token does not match.

    Usage:
        @authorization_required(app)
        def my_func_that_requires_authorization():
            ...
    """

    def inner(f):
        @wraps(f)
        def innerinner(*args, **kwargs):
            token = request.args.get("access_token", False)
            hs_token = app.config["hs_token"]
            if not token or token != hs_token:
                return jsonify({"errcode": "CHAT.CACTUS.APPSERVICE_FORBIDDEN"}), 403
            return f(*args, **kwargs)

        return innerinner

    return inner


@app.route("/transactions/<string:txn_id>", methods=["PUT"])  # deprecated
@app.route("/_matrix/app/v1/transactions/<string:txn_id>", methods=["PUT"])
@authorization_required(app)
def new_transaction(txn_id: str):
    events = request.get_json()["events"]
    for event in events:
        print(txn_id, event)
    return jsonify({})


@app.route("/rooms/<path:alias>", methods=["GET"])  # deprecated
@app.route("/_matrix/app/v1/rooms/<path:alias>", methods=["GET"])
@authorization_required(app)
def query_room_alias(alias: str):
    """Implement the Room Alias Query API from the appservice specification.

    The homeserver hits this endpoint to see if a room alias exists. We are
    only queried for rooms in our alias namespace. In our namespace, all rooms
    exist. Therefore, we MUST create the room before responding.

    Reference: https://matrix.org/docs/spec/application_service/r0.1.2#get-matrix-app-v1-rooms-roomalias
    """

    # Create room here. This can be done after we have implemented auth.
    print(alias)

    # 200, with an empty json object indicates that the room exists.
    return jsonify({}), 200
