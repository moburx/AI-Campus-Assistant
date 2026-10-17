"""Хичээл удирдах API-ийн тест."""


def test_course_is_created_automatically_with_assignment(client, user_headers, create_assignment):
    create_assignment(user_headers, course="Math")
    create_assignment(user_headers, course="Math")

    courses = client.get("/api/courses", headers=user_headers).json()

    assert len(courses) == 1
    assert courses[0]["name"] == "Math"
    assert courses[0]["total"] == 2
    assert courses[0]["completed"] == 0


def test_course_name_match_is_case_insensitive(client, user_headers, create_assignment):
    first = create_assignment(user_headers, course="Math")
    second = create_assignment(user_headers, course="math")

    assert first["course_id"] == second["course_id"]
    assert second["course"] == "Math"


def test_create_course_manually(client, user_headers):
    response = client.post(
        "/api/courses",
        json={"name": "Networks", "color": "#16A34A"},
        headers=user_headers,
    )
    data = response.json()

    assert response.status_code == 201
    assert data["name"] == "Networks"
    assert data["color"] == "#16a34a"
    assert data["total"] == 0


def test_create_course_gets_default_color(client, user_headers):
    data = client.post(
        "/api/courses", json={"name": "Networks"}, headers=user_headers
    ).json()
    assert data["color"].startswith("#") and len(data["color"]) == 7


def test_duplicate_course_returns_409(client, user_headers):
    client.post("/api/courses", json={"name": "Networks"}, headers=user_headers)
    response = client.post(
        "/api/courses", json={"name": "networks"}, headers=user_headers
    )
    assert response.status_code == 409


def test_invalid_color_returns_422(client, user_headers):
    response = client.post(
        "/api/courses",
        json={"name": "Art", "color": "red"},
        headers=user_headers,
    )
    assert response.status_code == 422


def test_rename_course_updates_assignments(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers, course="Math")

    response = client.patch(
        f"/api/courses/{assignment['course_id']}",
        json={"name": "Mathematics"},
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Mathematics"

    updated = client.get("/api/assignments", headers=user_headers).json()[0]
    assert updated["course"] == "Mathematics"


def test_rename_to_existing_name_returns_409(client, user_headers, create_assignment):
    math = create_assignment(user_headers, course="Math")
    create_assignment(user_headers, course="Art")

    response = client.patch(
        f"/api/courses/{math['course_id']}",
        json={"name": "ART"},
        headers=user_headers,
    )
    assert response.status_code == 409


def test_change_course_color(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers, course="Math")

    client.patch(
        f"/api/courses/{assignment['course_id']}",
        json={"color": "#db2777"},
        headers=user_headers,
    )

    updated = client.get("/api/assignments", headers=user_headers).json()[0]
    assert updated["course_color"] == "#db2777"


def test_delete_empty_course(client, user_headers):
    course = client.post(
        "/api/courses", json={"name": "Unused"}, headers=user_headers
    ).json()

    response = client.delete(f"/api/courses/{course['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get("/api/courses", headers=user_headers).json() == []


def test_cannot_delete_course_with_assignments(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers, course="Math")

    response = client.delete(
        f"/api/courses/{assignment['course_id']}",
        headers=user_headers,
    )
    assert response.status_code == 409


def test_courses_are_private_per_user(client, make_user, create_assignment):
    alice = make_user("alice")
    bob = make_user("bob")
    assignment = create_assignment(alice, course="Secret course")
    url = f"/api/courses/{assignment['course_id']}"

    assert client.get("/api/courses", headers=bob).json() == []
    assert client.patch(url, json={"name": "Taken"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404


def test_two_users_can_have_same_course_name(client, make_user, create_assignment):
    alice = make_user("alice")
    bob = make_user("bob")

    a = create_assignment(alice, course="Math")
    b = create_assignment(bob, course="Math")

    assert a["course_id"] != b["course_id"]


def test_course_counts_completed(client, user_headers, create_assignment):
    first = create_assignment(user_headers, course="Math")
    create_assignment(user_headers, course="Math")
    client.patch(
        f"/api/assignments/{first['id']}",
        json={"completed": True},
        headers=user_headers,
    )

    course = client.get("/api/courses", headers=user_headers).json()[0]
    assert course["total"] == 2
    assert course["completed"] == 1
