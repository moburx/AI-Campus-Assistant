"""Даалгаврын CRUD, засвар, шүүлт, хэрэглэгч хоорондын тусгаарлалтын тест."""

import pytest


def test_assignments_require_token(client):
    assert client.get("/api/assignments").status_code in (401, 403)
    assert client.post("/api/assignments", json={}).status_code in (401, 403)


def test_new_user_has_no_assignments(client, user_headers):
    response = client.get("/api/assignments", headers=user_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_create_assignment_with_defaults(user_headers, create_assignment):
    data = create_assignment(user_headers)

    assert data["title"] == "Python lab"
    assert data["course"] == "Programming"
    assert data["deadline"] == "2030-01-15"
    assert data["priority"] == "medium"
    assert data["notes"] == ""
    assert data["completed"] is False
    assert data["completed_at"] is None
    assert data["course_id"] is not None
    assert data["course_color"].startswith("#")


def test_create_assignment_with_priority_and_notes(user_headers, create_assignment):
    data = create_assignment(
        user_headers,
        priority="high",
        notes="  Read chapter 3 first  ",
    )

    assert data["priority"] == "high"
    assert data["notes"] == "Read chapter 3 first"


def test_create_trims_whitespace(user_headers, create_assignment):
    data = create_assignment(user_headers, title="  Essay  ", course="  Writing ")
    assert data["title"] == "Essay"
    assert data["course"] == "Writing"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "course": "Math", "deadline": "2030-01-01"},
        {"title": "A", "course": "", "deadline": "2030-01-01"},
        {"title": "   ", "course": "Math", "deadline": "2030-01-01"},
        {"title": "A", "course": "Math", "deadline": "stringstri"},
        {"title": "A", "course": "Math", "deadline": "2030-13-40"},
        {"title": "A", "course": "Math", "deadline": "2030-01-01", "priority": "urgent"},
        {"title": "A", "course": "Math", "deadline": "2030-01-01", "notes": "x" * 1001},
        {"title": "A", "course": "Math"},
    ],
)
def test_create_invalid_assignment_returns_422(client, user_headers, payload):
    response = client.post("/api/assignments", json=payload, headers=user_headers)
    assert response.status_code == 422


def test_list_returns_newest_first(client, user_headers, create_assignment):
    first = create_assignment(user_headers, title="First")
    second = create_assignment(user_headers, title="Second")

    ids = [item["id"] for item in client.get(
        "/api/assignments", headers=user_headers
    ).json()]

    assert ids == [second["id"], first["id"]]


def test_complete_and_uncomplete(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers)
    url = f"/api/assignments/{assignment['id']}"

    done = client.patch(url, json={"completed": True}, headers=user_headers).json()
    assert done["completed"] is True
    assert done["completed_at"] is not None

    undone = client.patch(url, json={"completed": False}, headers=user_headers).json()
    assert undone["completed"] is False
    assert undone["completed_at"] is None


def test_completing_twice_keeps_first_completion_time(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers)
    url = f"/api/assignments/{assignment['id']}"

    first = client.patch(url, json={"completed": True}, headers=user_headers).json()
    second = client.patch(url, json={"completed": True}, headers=user_headers).json()

    assert second["completed_at"] == first["completed_at"]


def test_edit_title_deadline_priority_notes(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers)

    response = client.patch(
        f"/api/assignments/{assignment['id']}",
        json={
            "title": "Python lab 2",
            "deadline": "2030-02-01",
            "priority": "low",
            "notes": "Updated",
        },
        headers=user_headers,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["title"] == "Python lab 2"
    assert data["deadline"] == "2030-02-01"
    assert data["priority"] == "low"
    assert data["notes"] == "Updated"
    # Илгээгээгүй талбар өөрчлөгдөхгүй.
    assert data["course"] == "Programming"
    assert data["completed"] is False


def test_edit_course_moves_assignment_to_new_course(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers, course="Math")

    data = client.patch(
        f"/api/assignments/{assignment['id']}",
        json={"course": "Physics"},
        headers=user_headers,
    ).json()

    assert data["course"] == "Physics"
    assert data["course_id"] != assignment["course_id"]

    names = {course["name"] for course in client.get(
        "/api/courses", headers=user_headers
    ).json()}
    assert {"Math", "Physics"} <= names


def test_edit_with_empty_body_returns_422(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers)
    response = client.patch(
        f"/api/assignments/{assignment['id']}",
        json={},
        headers=user_headers,
    )
    assert response.status_code == 422


def test_edit_with_invalid_deadline_returns_422(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers)
    response = client.patch(
        f"/api/assignments/{assignment['id']}",
        json={"deadline": "not-a-date"},
        headers=user_headers,
    )
    assert response.status_code == 422


def test_delete_assignment(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers)
    url = f"/api/assignments/{assignment['id']}"

    assert client.delete(url, headers=user_headers).status_code == 204
    assert client.get("/api/assignments", headers=user_headers).json() == []
    assert client.delete(url, headers=user_headers).status_code == 404


def test_update_missing_assignment_returns_404(client, user_headers):
    response = client.patch(
        "/api/assignments/9999",
        json={"completed": True},
        headers=user_headers,
    )
    assert response.status_code == 404


def test_filter_by_status(client, user_headers, create_assignment):
    open_item = create_assignment(user_headers, title="Open")
    done_item = create_assignment(user_headers, title="Done")
    client.patch(
        f"/api/assignments/{done_item['id']}",
        json={"completed": True},
        headers=user_headers,
    )

    completed = client.get(
        "/api/assignments?status=completed", headers=user_headers
    ).json()
    incomplete = client.get(
        "/api/assignments?status=incomplete", headers=user_headers
    ).json()

    assert [item["id"] for item in completed] == [done_item["id"]]
    assert [item["id"] for item in incomplete] == [open_item["id"]]


def test_filter_by_course(client, user_headers, create_assignment):
    math = create_assignment(user_headers, course="Math")
    create_assignment(user_headers, course="Art")

    response = client.get(
        f"/api/assignments?course_id={math['course_id']}",
        headers=user_headers,
    ).json()

    assert [item["id"] for item in response] == [math["id"]]


# ---------- Хэрэглэгч хоорондын тусгаарлалт ----------
def test_users_only_see_their_own_assignments(client, make_user, create_assignment):
    alice = make_user("alice")
    bob = make_user("bob")

    create_assignment(alice, title="Alice task")

    assert client.get("/api/assignments", headers=bob).json() == []
    assert len(client.get("/api/assignments", headers=alice).json()) == 1


def test_user_cannot_modify_other_users_assignment(client, make_user, create_assignment):
    alice = make_user("alice")
    bob = make_user("bob")
    assignment = create_assignment(alice)
    url = f"/api/assignments/{assignment['id']}"

    assert client.patch(url, json={"completed": True}, headers=bob).status_code == 404
    assert client.patch(url, json={"title": "Hacked"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404

    still_there = client.get("/api/assignments", headers=alice).json()[0]
    assert still_there["title"] == "Python lab"
    assert still_there["completed"] is False
