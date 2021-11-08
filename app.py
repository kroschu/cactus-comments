from functools import lru_cache, wraps
import logging
import os
import random
import re
import sys
import urllib

from flask import Blueprint, Flask, current_app, jsonify, request
import requests


appservice_bp = Blueprint("appservice_endpoints", __name__)


CONFIG_ERROR_EXITCODE = 2


HELP_MSG = """\
🌵 Hi I'm here to help you with Cactus Comments (https://cactus.chat) 🌵

To get started, register a site by typing:

    register <sitename>

Where <sitename> is replaced by any name you like. The site ensures that\
 you are moderator in your comment sections 👮‍♀️

After you have registered a site, go to \
https://cactus.chat/docs/getting-started/introduction/ to learn how to embed \
comment sections wherever you like!
"""

MODERATION_EXPLANATION = """\
Hi there! You just registered a Cactus Comments site 🌵

Visit https://cactus.chat/ to get help embedding your comment sections anywhere!

My task here is simple: I'm here to help ease moderation of your comment \
sections!

🚨 If you ban someone from one of your comment sections, I'll make sure \
they're banned from all of your comment sections 👊 If you add a moderator to \
this room, I'll make sure they have the same permissions across all your \
comment sections 👮‍♀️👮‍♂️
"""


def create_app(
    hs_token,
    as_token,
    homeserver,
    user_id,
    namespace_regex,
    namespace_prefix,
    register_user_regex,
):
    app = Flask(__name__)
    app.register_blueprint(appservice_bp)
    app.logger.setLevel(logging.INFO)

    app.config["hs_token"] = hs_token
    app.config["as_token"] = as_token
    app.config["homeserver"] = homeserver
    app.config["user_id"] = user_id
    app.config["namespace_regex"] = namespace_regex
    app.config["namespace"] = namespace_prefix
    app.config["register_user_regex"] = register_user_regex

    app.config["auth_header"] = {"Authorization": f"Bearer {as_token}"}

    app.logger.info("Created application!")

    return app


def create_app_from_env():
    hs_token = os.getenv("CACTUS_HS_TOKEN")
    as_token = os.getenv("CACTUS_AS_TOKEN")
    homeserver = os.getenv("CACTUS_HOMESERVER_URL")
    user_id = os.getenv("CACTUS_USER_ID")
    namespace_regex = os.getenv("CACTUS_NAMESPACE_REGEX", r"#comments_.*")
    namespace_prefix = os.getenv("CACTUS_NAMESPACE_PREFIX", "comments_")
    register_user_regex = os.getenv("CACTUS_REGISTRATION_REGEX", r"@.*:.*")

    if hs_token is None:
        print("No homeserver token provided (CACTUS_HS_TOKEN).", file=sys.stderr)
        sys.exit(CONFIG_ERROR_EXITCODE)

    if as_token is None:
        print("No appservice token provided (CACTUS_AS_TOKEN).", file=sys.stderr)
        sys.exit(CONFIG_ERROR_EXITCODE)

    if homeserver is None:
        print("No homeserver url provided (CACTUS_HOMESERVER_URL).", file=sys.stderr)
        sys.exit(CONFIG_ERROR_EXITCODE)

    homeserver = homeserver.removesuffix("/")
    if not (homeserver.startswith("http://") or homeserver.startswith("https://")):
        print(
            "Homeserver url missing http/s scheme (CACTUS_HOMESERVER_URL).",
            file=sys.stderr,
        )
        sys.exit(CONFIG_ERROR_EXITCODE)

    if namespace_regex is None:
        print("No namespace regex provided (CACTUS_NAMESPACE_REGEX).", file=sys.stderr)
        sys.exit(CONFIG_ERROR_EXITCODE)

    if namespace_prefix is None:
        print(
            "No namespace prefix provided (CACTUS_NAMESPACE_PREFIX).", file=sys.stderr
        )
        sys.exit(CONFIG_ERROR_EXITCODE)

    if not namespace_regex[1:].startswith(namespace_prefix):
        print("Namespace regex should start with the namespace prefix")
        sys.exit(CONFIG_ERROR_EXITCODE)

    return create_app(
        hs_token,
        as_token,
        homeserver,
        user_id,
        namespace_regex,
        namespace_prefix,
        register_user_regex,
    )


def matrix_error(error_code, http_code, error_msg=None):
    if error_msg is None:
        current_app.logger.info("%s %s", http_code, error_code)
        return jsonify({"errcode": error_code}), http_code
    current_app.logger.info("%s %s: %s", http_code, error_code, error_msg)
    return jsonify({"errcode": error_code, "error": error_msg}), http_code


def send_plaintext_msg(room_id, msg):
    txn_id = random.randint(0, 1_000_000_000)
    return requests.put(
        current_app.config["homeserver"]
        + f"/_matrix/client/r0/rooms/{room_id}/send/m.room.message/{txn_id}",
        headers=current_app.config["auth_header"],
        json={"msgtype": "m.text", "body": msg},
    )


def alias_to_mod_room_id(alias):
    """Convert any room alias to the mod room id for its' site."""
    splitting_colon = alias.index(":")
    last_underscore = alias.rindex("_", 0, splitting_colon)
    mod_alias = urllib.parse.quote(alias[:last_underscore] + alias[splitting_colon:])
    return requests.get(
        current_app.config["homeserver"]
        + f"/_matrix/client/r0/directory/room/{mod_alias}",
        headers=current_app.config["auth_header"],
    )


@lru_cache(maxsize=10000)
def canonical_room_alias(room_id):
    """Get the canonical room alias (or None) from a room id."""
    r = requests.get(
        current_app.config["homeserver"]
        + f"/_matrix/client/r0/rooms/{room_id}/state/m.room.canonical_alias",
        headers=current_app.config["auth_header"],
    )
    if not r.ok or "alias" not in r.json():
        return None
    return r.json()["alias"]


def is_comment_section_room(alias):
    # There has to be exactly one more underscore in alias, than in the
    # appservice namespace. Otherwise, it is a moderation room or an invalid
    # alias.
    return current_app.config["namespace"].count("_") + 1 == alias.count("_")


def is_moderation_room(alias):
    if current_app.config["namespace"].count("_") != alias.count("_"):
        return False
    namespace_regex = current_app.config["namespace_regex"]
    return re.match(namespace_regex, alias) is not None


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
            return matrix_error("CHAT.CACTUS.APPSERVICE_UNAUTHORIZED", 401)
        if token != hs_token:
            return matrix_error("CHAT.CACTUS.APPSERVICE_FORBIDDEN", 403)
        return f(*args, **kwargs)

    return inner


def localpart_from_user_id(user_id):
    # https://matrix.org/docs/spec/appendices#user-identifiers
    return re.match(r"^@([a-zA-Z0-9._=/-]+):", user_id).group(1)


def localpart_from_alias(alias):
    """Return the localpart of a room alias."""
    return alias.split(":")[0]


def sitename_from_localpart(alias_localpart):
    """Return the sitename of the localpart of an alias."""
    last_underscore = alias_localpart.rindex("_")
    sitename_start_index = alias_localpart.rindex("_", 0, last_underscore) + 1
    return alias_localpart[sitename_start_index:last_underscore]


def comment_section_id_from_localpart(alias_localpart):
    """Return the comment section id of the localpart of an alias."""
    last_underscore = alias_localpart.rindex("_")
    return alias_localpart[last_underscore + 1 :]


def is_user_allowed_register(user_id):
    return re.match(current_app.config["register_user_regex"], user_id) is not None


def make_sure_user_is_registered():
    # Apparently, there are no `before_first_request` on blueprints. Therefore,
    # we abuse the app config a bit, so this function can be called many times
    # but only really runs the first time.
    if not current_app.config.get("registered", False):
        # First time running

        user_id = current_app.config["user_id"]

        # Register user
        r = requests.post(
            current_app.config["homeserver"] + "/_matrix/client/r0/register",
            json={
                "username": localpart_from_user_id(user_id),
                "type": "m.login.application_service",
            },
            params={"kind": "user"},
            headers=current_app.config["auth_header"],
        )
        if not (r.ok or r.json()["errcode"] == "M_USER_IN_USE"):
            raise ValueError("Failed to register user.")

        # Change display name
        requests.put(
            current_app.config["homeserver"]
            + f"/_matrix/client/r0/profile/{user_id}/displayname",
            json={"displayname": "Cactus Comments"},
            headers=current_app.config["auth_header"],
        )

        # Change avatar / profile image
        requests.put(
            current_app.config["homeserver"]
            + f"/_matrix/client/r0/profile/{user_id}/avatar_url",
            json={"avatar_url": "mxc://matrix.org/gdgXnTHPpGqCsIPAaUNgoHHV"},
            headers=current_app.config["auth_header"],
        )

        current_app.config["registered"] = True


@appservice_bp.route("/transactions/<string:txn_id>", methods=["PUT"])  # deprecated
@appservice_bp.route("/_matrix/app/v1/transactions/<string:txn_id>", methods=["PUT"])
@authorization_required
def new_transaction(txn_id: str):
    """Implement the Push API from the appservice specification.

    The homeserver hits this endpoint to notify us of new events in our rooms.

    Reference: https://matrix.org/docs/spec/application_service/r0.1.2#put-matrix-app-v1-transactions-txnid
    """

    make_sure_user_is_registered()

    events = request.get_json()["events"]

    for event in events:
        room_id = event["room_id"]
        if event["type"] == "m.room.member":
            is_invite = event["content"]["membership"] == "invite"
            is_for_me = event["state_key"] == current_app.config["user_id"]
            if is_invite and is_for_me:
                if is_user_allowed_register(event["sender"]):
                    current_app.logger.info(
                        "Accepting invite    room_id=%r sender=%r",
                        room_id,
                        event["sender"],
                    )
                    # Accept invite / join room
                    r = requests.post(
                        current_app.config["homeserver"]
                        + f"/_matrix/client/r0/rooms/{room_id}/join",
                        headers=current_app.config["auth_header"],
                        json={},
                    )
                else:
                    current_app.logger.info(
                        "Rejecting invite    room_id=%r sender=%r",
                        room_id,
                        event["sender"],
                    )
                    # Reject invite
                    r = requests.post(
                        current_app.config["homeserver"]
                        + f"/_matrix/client/r0/rooms/{room_id}/leave",
                        headers=current_app.config["auth_header"],
                        json={},
                    )

            elif event["content"]["membership"] == "ban":
                alias = canonical_room_alias(event["room_id"])
                if not alias:
                    continue
                if is_comment_section_room(alias):
                    # Make sure the user is also banned in the moderation room
                    r_mod_room = alias_to_mod_room_id(alias)
                    room_id = r_mod_room.json()["room_id"]
                    user_to_ban = event["state_key"]
                    requests.post(
                        current_app.config["homeserver"]
                        + f"/_matrix/client/r0/rooms/{room_id}/ban",
                        headers=current_app.config["auth_header"],
                        json={"user_id": user_to_ban},
                    )
                elif is_moderation_room(alias):
                    # Ban event in a moderation room. Replicate to all rooms
                    # for this site.

                    # At this point it is very clear that our current
                    # implementation architecture does not scale.. :-)

                    mod_alias = alias  # for readability below
                    user_to_ban = event["state_key"]
                    current_app.logger.info(
                        "Ban in mod room, replicating    room=%r user_to_ban=%r",
                        mod_alias,
                        user_to_ban,
                    )
                    joined_rooms = requests.get(
                        current_app.config["homeserver"]
                        + "/_matrix/client/r0/joined_rooms",
                        headers=current_app.config["auth_header"],
                    ).json()["joined_rooms"]
                    for room_id in joined_rooms:
                        room_alias = canonical_room_alias(room_id)
                        if not room_alias:
                            continue
                        room_alias_localpart = localpart_from_alias(room_alias)
                        mod_alias_localpart = localpart_from_alias(mod_alias)
                        if room_alias != mod_alias and room_alias_localpart.startswith(
                            mod_alias_localpart
                        ):
                            requests.post(
                                current_app.config["homeserver"]
                                + f"/_matrix/client/r0/rooms/{room_id}/ban",
                                headers=current_app.config["auth_header"],
                                json={"user_id": user_to_ban},
                            )

        elif event["type"] == "m.room.power_levels":
            mod_alias = canonical_room_alias(event["room_id"])
            if not mod_alias:
                continue
            if is_moderation_room(mod_alias):
                current_app.logger.info(
                    "Power level changed, replicating    room=%r", mod_alias
                )
                # When power_levels are changed in the moderation room, we want
                # to replicate it to all rooms for the site
                power_levels = event["content"]
                joined_rooms = requests.get(
                    current_app.config["homeserver"]
                    + "/_matrix/client/r0/joined_rooms",
                    headers=current_app.config["auth_header"],
                ).json()["joined_rooms"]
                for room_id in joined_rooms:
                    room_alias = canonical_room_alias(room_id)
                    if not room_alias:
                        continue
                    room_alias_localpart = localpart_from_alias(room_alias)
                    mod_alias_localpart = localpart_from_alias(mod_alias)
                    if room_alias != mod_alias and room_alias_localpart.startswith(
                        mod_alias_localpart
                    ):
                        requests.put(
                            current_app.config["homeserver"]
                            + f"/_matrix/client/r0/rooms/{room_id}/state/m.room.power_levels",
                            headers=current_app.config["auth_header"],
                            json=power_levels,
                        )

        elif event["type"] == "m.room.message":
            if event["content"].get("msgtype") != "m.text":
                continue
            msg = event["content"]["body"]
            if not (msg == "help" or msg.startswith("register")):
                # Only react to "help" and "register <sitename>" messages
                continue

            # Only interact with anyone in the `CACTUS_REGISTRATION_REGEX`
            if not is_user_allowed_register(event["sender"]):
                continue

            # Make sure we don't respond to comments
            alias = canonical_room_alias(room_id)
            if alias:
                namespace_regex = current_app.config["namespace_regex"]
                if re.match(namespace_regex, alias) is not None:
                    continue

            if msg == "help":
                send_plaintext_msg(room_id, HELP_MSG)
                continue

            command = msg.split(" ")
            if len(command) != 2:
                error_msg = 'To register a site, type "register <sitename>"'
                send_plaintext_msg(room_id, error_msg)
                continue

            sitename = command[1]

            if not sitename:
                error_msg = 'To register a site, type "register <sitename>"'
                send_plaintext_msg(room_id, error_msg)
                continue

            if "_" in sitename:
                error_msg = 'Sorry, underscore ("_") is not allowed in site names'
                send_plaintext_msg(room_id, error_msg)
                continue

            # Try to create, will fail if already exists
            r = requests.post(
                current_app.config["homeserver"] + "/_matrix/client/r0/createRoom",
                headers=current_app.config["auth_header"],
                json={
                    "visibility": "private",
                    "room_alias_name": current_app.config["namespace"] + sitename,
                    "name": f"{sitename} moderation room",
                    "topic": f"Moderation room for {sitename}. For more, visit https://cactus.chat",
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
                    msg = f"Sorry, {sitename} is already used by someone else."
                    send_plaintext_msg(room_id, msg)
                    continue
                else:
                    error_msg = rjson.get("error", "no error message")
                    current_app.logger.warning(
                        "Failed to create site with unknown error    error=%r",
                        error_msg,
                    )
                    msg = f"Unknown error. Error from homeserver: {error_msg}."
                    send_plaintext_msg(room_id, msg)
                    continue

            current_app.logger.info(
                "Created site    name=%r owner=%r", sitename, event["sender"]
            )

            send_plaintext_msg(room_id, f"Created site {sitename} for you 🚀")
            send_plaintext_msg(rjson["room_id"], MODERATION_EXPLANATION)

    return jsonify({}), 200


@appservice_bp.route("/rooms/<path:alias>", methods=["GET"])  # deprecated
@appservice_bp.route("/_matrix/app/v1/rooms/<path:alias>", methods=["GET"])
@authorization_required
def query_room_alias(alias: str):
    """Implement the Room Alias Query API from the appservice specification.

    The homeserver hits this endpoint to see if a room alias exists. We are
    only queried for rooms in our alias namespace. Therefore, we MUST create
    *comment section* rooms (for registered sites) before responding.

    Reference: https://matrix.org/docs/spec/application_service/r0.1.2#get-matrix-app-v1-rooms-roomalias
    """

    make_sure_user_is_registered()

    if not is_comment_section_room(alias):
        return matrix_error("CHAT.CACTUS.APPSERVICE_NOT_FOUND", 404)

    r_mod_id = alias_to_mod_room_id(alias)
    if not r_mod_id.ok:
        # Site does not exist.
        return matrix_error("CHAT.CACTUS.APPSERVICE_NOT_FOUND", 404)

    # Now we know that this is a query for a valid comment section room. We
    # must create it, if it does not exist.

    mod_room_id = r_mod_id.json()["room_id"]

    # Get power levels from moderation room
    r_power_level = requests.get(
        current_app.config["homeserver"]
        + f"/_matrix/client/r0/rooms/{mod_room_id}/state/m.room.power_levels",
        headers=current_app.config["auth_header"],
    )

    # Create room
    alias_localpart = localpart_from_alias(alias)
    sitename = sitename_from_localpart(alias_localpart)
    comment_section_id = comment_section_id_from_localpart(alias_localpart)
    r = requests.post(
        current_app.config["homeserver"] + "/_matrix/client/r0/createRoom",
        headers=current_app.config["auth_header"],
        json={
            "visibility": "private",
            "name": f"{sitename} comment section ({comment_section_id})",
            "room_alias_name": alias_localpart[1:],  # strip leading hashtag
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
            # Replicate power level from site moderation room
            "power_level_content_override": r_power_level.json(),
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
        return matrix_error(
            "CHAT.CACTUS.APPSERVICE_NOT_FOUND",
            404,
            f"Unknown error. Error from homeserver: {homeserver_err_msg}.",
        )

    # Get banned users from moderation room
    r_banned_users = requests.get(
        current_app.config["homeserver"]
        + f"/_matrix/client/r0/rooms/{mod_room_id}/state",
        headers=current_app.config["auth_header"],
    )
    # Send ban events, one at a time...
    room_id = r.json()["room_id"]
    for state in r_banned_users.json():
        if state["type"] != "m.room.member":
            continue
        if state["content"]["membership"] == "ban":
            requests.post(
                current_app.config["homeserver"]
                + f"/_matrix/client/r0/rooms/{room_id}/ban",
                headers=current_app.config["auth_header"],
                json={"user_id": state["state_key"]},
            )

    # 200, with an empty json object indicates that the room exists.
    return jsonify({}), 200
