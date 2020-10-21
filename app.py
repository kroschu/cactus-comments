from flask import Flask, jsonify, request


app = Flask(__name__)


@app.route("/transactions/<string:txn_id>", methods=["PUT"])  # deprecated
@app.route("/_matrix/app/v1/transactions/<string:txn_id>", methods=["PUT"])
def new_transaction(txn_id: str):
    events = request.get_json()["events"]
    for event in events:
        print(txn_id, event)
    return jsonify({})


@app.route("/rooms/<path:alias>", methods=["GET"])  # deprecated
@app.route("/_matrix/app/v1/rooms/<path:alias>", methods=["GET"])
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
