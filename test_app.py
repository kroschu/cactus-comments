import os
import pytest
import random
import requests
import uuid

from app import create_app_from_env


@pytest.fixture
def homeserver_url():
    return os.environ["CACTUS_HOMESERVER_URL"]


def sign_in(homeserver_url, username):
    userid, password = f"@{username}:localhost:8008", username

    # log in
    r = requests.post(
        f"{homeserver_url}/_matrix/client/r0/login",
        json={
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": userid},
            "password": password,
        },
    )
    assert r.status_code == 200, f"Login as {userid} failed: {r.status_code}"
    access_token = r.json()["access_token"]
    server_name = r.json()["home_server"]
    headers = {"Authorization": f"Bearer {access_token}"}
    return access_token


@pytest.fixture
def dev1(homeserver_url):
    return sign_in(homeserver_url, "dev1")


@pytest.fixture
def dev2(homeserver_url):
    return sign_in(homeserver_url, "dev2")


@pytest.fixture
def sitename(homeserver_url, dev1):
    """Register `sitename` as user "dev1"."""
    sitename = str(uuid.uuid4())
    server_name = "localhost:8008"
    userid, password = "@dev1:localhost:8008", "dev1"
    access_token = dev1
    headers = {"Authorization": f"Bearer {access_token}"}

    # create a new room
    r = requests.post(
        f"{homeserver_url}/_matrix/client/r0/createRoom",
        json={"preset": "private_chat"},
        headers=headers,
    )
    assert r.status_code == 200
    room_id = r.json()["room_id"]

    # invite cactusbot to the room
    cactusbot_userid = f"@cactusbot:{server_name}"
    r = requests.post(
        f"{homeserver_url}/_matrix/client/r0/rooms/{room_id}/invite",
        json={"user_id": cactusbot_userid},
        headers=headers,
    )
    errmsg = f"Error inviting {cactusbot_userid}: {r.json()}"
    assert r.status_code == 200, errmsg

    # wait for cactusbot to join
    joined = False
    while not joined:
        r = requests.get(
            f"{homeserver_url}/_matrix/client/r0/rooms/{room_id}/state/m.room.member/{cactusbot_userid}",
            headers=headers,
        )
        assert r.status_code == 200
        joined = r.json()["membership"] == "join"

    # send "register" message
    r = requests.put(
        f"{homeserver_url}/_matrix/client/r0/rooms/{room_id}/send/m.room.message/{random.random()}",
        json={"msgtype": "m.text", "body": f"register {sitename}"},
        headers=headers,
    )
    assert r.status_code == 200, f"Failed sending message: {r.json()}"

    # check for response
    cactusbot_messages = []
    next_batch = None
    while not cactusbot_messages:
        url = f"{homeserver_url}/_matrix/client/r0/sync"
        if isinstance(next_batch, str):
            url = f"{url}?since={next_batch}"
        r = requests.get(url, headers=headers)
        assert r.status_code == 200
        events = r.json()["rooms"]["join"][room_id]["timeline"]["events"]
        for e in events:
            if e["sender"] == cactusbot_userid and e["type"] == "m.room.message":
                cactusbot_messages.append(e)
    assert len(cactusbot_messages) == 1
    msg_body = cactusbot_messages[0]["content"]["body"]
    expected_body = f"Created site {sitename} for you 🚀"
    assert msg_body == expected_body

    return sitename


@pytest.fixture
def appservice():
    app = create_app_from_env()

    with app.test_client() as c:

        def authorized_request(*args, **kwargs):
            # Inject access token in query string
            query = kwargs.get("query_string", {})
            query["access_token"] = app.config["hs_token"]
            kwargs["query_string"] = query
            return c.open(*args, **kwargs)

        c.authorized_request = authorized_request
        yield c


def test_query_room_alias_200(appservice, sitename):
    r = appservice.authorized_request(
        f"/_matrix/app/v1/rooms/%23comments_{sitename}_there:localhost:8008"
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_slashed(appservice, sitename):
    r = appservice.authorized_request(
        f"/_matrix/app/v1/rooms/%23comments_{sitename}_t/here:localhost:8008"
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_servername_with_underscore(appservice, sitename):
    r = appservice.authorized_request(
        f"/_matrix/app/v1/rooms/%23comments_{sitename}_there:localhost:8008"
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_too_few_underscores(appservice, sitename):
    r = appservice.authorized_request(
        f"/_matrix/app/v1/rooms/%23comments_{sitename}there:localhost:8008"
    )
    assert r.status_code == 404
    assert r.get_json() == {"errcode": "CHAT.CACTUS.APPSERVICE_NOT_FOUND"}


def test_query_room_alias_too_many_underscores(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_hi_there_friend:localhost:8008"
    )
    assert r.status_code == 404
    assert r.get_json() == {"errcode": "CHAT.CACTUS.APPSERVICE_NOT_FOUND"}


def test_query_room_alias_already_exists(appservice, sitename):
    # Make sure that we can join rooms that already exists
    r1 = appservice.authorized_request(
        f"/_matrix/app/v1/rooms/%23comments_{sitename}_post0:localhost:8008"
    )
    assert r1.status_code == 200
    assert r1.get_json() == {}
    r2 = appservice.authorized_request(
        f"/_matrix/app/v1/rooms/%23comments_{sitename}_post0:localhost:8008"
    )
    assert r2.status_code == 200
    assert r2.get_json() == {}


def test_push_api_empty_success(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/transactions/42",
        method="PUT",
        json={"events": []},
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_unauthorized_query_room_alias(appservice):
    r = appservice.get("/_matrix/app/v1/rooms/comments_hi_there:servername")
    assert r.status_code == 401
    assert r.get_json() == {"errcode": "CHAT.CACTUS.APPSERVICE_UNAUTHORIZED"}


def test_unauthorized_push_api_call(appservice):
    r = appservice.put(
        "/_matrix/app/v1/transactions/42",
        query_string={"access_token": "not_the_real_access_token"},
        json={"events": []},
    )
    assert r.status_code == 403
    assert r.get_json() == {"errcode": "CHAT.CACTUS.APPSERVICE_FORBIDDEN"}


def test_unauthorized_push_api_call_empty_token(appservice):
    r = appservice.put(
        "/_matrix/app/v1/transactions/42",
        query_string={"access_token": ""},
        json={"events": []},
    )
    assert r.status_code == 401
    assert r.get_json() == {"errcode": "CHAT.CACTUS.APPSERVICE_UNAUTHORIZED"}


def test_auto_invite(homeserver_url, appservice, sitename, dev1, dev2):
    """ When the appservice creates a new room,
        the mod room participants are invited to it """

    # get the appservice to make a new room
    random_id = str(uuid.uuid4())[:8]
    encoded_alias = f"%23comments_{sitename}_{random_id}%3Alocalhost%3A8008"
    r = appservice.authorized_request(
        f"/_matrix/app/v1/rooms/{encoded_alias}"
    )
    assert r.status_code == 200
    assert r.get_json() == {}

    # first, join as dev2...
    r = requests.post(
        f"{homeserver_url}/_matrix/client/v3/join/{encoded_alias}",
        headers={"Authorization": f"Bearer {dev2}"}
    )
    assert r.status_code == 200
    room_id = r.json()["room_id"]

    # ...then get the membership state event for dev1
    r = requests.get(
        f"{homeserver_url}/_matrix/client/v3/rooms/{room_id}/state/m.room.member/%40dev1%3Alocalhost%3A8008",
        headers={"Authorization": f"Bearer {dev2}"}
    )
    assert r.status_code == 200, r.json()
    assert r.json()["membership"] == "invite", "dev1 was not invited"
