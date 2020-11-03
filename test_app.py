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
    r = appservice.authorized_request("/_matrix/app/v1/rooms/_comments_hi_there")
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_slashed(appservice):
    r = appservice.authorized_request("/_matrix/app/v1/rooms/_comments_hi/there")
    assert r.status_code == 200
    assert r.get_json() == {}


def test_push_api_empty_success(appservice):
    r = appservice.authorized_request(
        "/_matrix/app/v1/transactions/42", method="PUT", json={"events": []},
    )
    assert r.status_code == 200
    assert r.get_json() == {}


def test_unauthorized_query_room_alias(appservice):
    r = appservice.get("/_matrix/app/v1/rooms/_comments_hi_there")
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
