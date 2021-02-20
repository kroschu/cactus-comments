import pytest

from app import app


@pytest.fixture
def appservice():
    with app.test_client() as c:

        def authorized_request(*args, **kwargs):
            # Inject access token in query string
            query = kwargs.get("query_string", {})
            query["access_token"] = app.config["hs_token"]
            kwargs["query_string"] = query

            return c.open(*args, **kwargs)

        c.authorized_request = authorized_request
        yield c


def test_query_room_alias_200(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_hi_there:servername"
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_slashed(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_hi_t/here:servername"
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_servername_with_underscore(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_hi_there:server_name"
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_too_few_underscores(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_hithere:servername"
    )
    assert r.status_code == 404
    assert r.get_json() == {"errcode": "CHAT.CACTUS.APPSERVICE_NOT_FOUND"}


def test_query_room_alias_too_many_underscores(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_hi_there_friend:servername"
    )
    assert r.status_code == 404
    assert r.get_json() == {"errcode": "CHAT.CACTUS.APPSERVICE_NOT_FOUND"}


def test_query_room_alias_already_exists(appservice):
    # Make sure that we can join rooms that already exists
    r1 = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_blog_post0:servername"
    )
    assert r1.status_code == 200
    assert r1.get_json() == {}
    r2 = appservice.authorized_request(
        "/_matrix/app/v1/rooms/%23comments_blog_post0:servername"
    )
    assert r2.status_code == 200
    assert r2.get_json() == {}


def test_push_api_empty_success(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/transactions/42", method="PUT", json={"events": []},
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
