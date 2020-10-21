import pytest

from app import app


@pytest.fixture
def appservice():
    with app.test_client() as c:
        yield c


def test_query_room_alias_200(appservice):
    r = appservice.get("/_matrix/app/v1/rooms/_comments_hi_there")
    assert r.status_code == 200
    assert r.get_json() == {}


def test_query_room_alias_slashed(appservice):
    r = appservice.get("/_matrix/app/v1/rooms/_comments_hi/there")
    assert r.status_code == 200
    assert r.get_json() == {}


def test_push_api_empty_success(appservice):
    r = appservice.put(
        "/_matrix/app/v1/transactions/42",
        json={"events": []},
    )
    assert r.status_code == 200
    assert r.get_json() == {}
