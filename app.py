from flask import Flask, jsonify, request


app = Flask(__name__)


@app.route("/transactions/<string:txn_id>", methods=["PUT"])  # deprecated
@app.route("/_matrix/app/v1/transactions/<string:txn_id>", methods=["PUT"])
def new_transaction(txn_id: str):
    events = request.get_json()["events"]
    for event in events:
        print(txn_id, event)
    return jsonify({})
