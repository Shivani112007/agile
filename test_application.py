import application as a

def test_match_score():
    assert a.match_score(["Python", "AWS"], ["python", "aws", "docker", "git"]) == 50
    assert a.match_score([], ["x"]) == 0
    assert a.match_score(["x"], []) == 0

def test_health():
    assert a.app.test_client().get("/health").get_json() == {"status": "ok"}

def test_full_flow():
    admin, stu = a.app.test_client(), a.app.test_client()
    admin.post("/register", data={"name": "Admin", "email": "admin@portal.com", "password": "password"})
    admin.post("/admin", data={"title": "Cloud Intern", "org": "Acme", "type": "Internship", "skills": "AWS, Python"})
    stu.post("/register", data={"name": "Shivani", "email": "s@x.com", "password": "password"})
    stu.post("/profile", data={"skills": "aws, java"})
    r = stu.get("/opportunities")
    assert b"Cloud Intern" in r.data and b"50%" in r.data
    oid = a.db.all("opportunities")[0]["id"]
    stu.post(f"/apply/{oid}")
    assert b"Submitted" in stu.get("/applications").data
