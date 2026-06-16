"""API integration test for Semantic Ticket Retrieval & Priority Prediction System."""
import httpx
import sys

base = "http://localhost:8000"
errors = []

def test(name, fn):
    try:
        fn()
        print(f"  PASS: {name}")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"  FAIL: {name} — {e}")

print("Running API tests...\n")

# 1. Health check
def t_health():
    r = httpx.get(f"{base}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"
test("Health check", t_health)

# 2. Login as agent
agent_token = None
def t_login_agent():
    global agent_token
    r = httpx.post(f"{base}/api/auth/login", json={"email": "som@support.com", "password": "password123"})
    assert r.status_code == 200
    agent_token = r.json()["access_token"]
    assert len(agent_token) > 20
test("Login (agent)", t_login_agent)

agent_headers = {}

# 3. Get profile
def t_profile():
    agent_headers["Authorization"] = f"Bearer {agent_token}"
    r = httpx.get(f"{base}/api/auth/me", headers=agent_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "agent"
    assert r.json()["name"] == "Som Tomar"
test("Get profile", t_profile)

# 4. Login as customer
cust_token = None
def t_login_customer():
    global cust_token
    r = httpx.post(f"{base}/api/auth/login", json={"email": "rahul@example.com", "password": "password123"})
    assert r.status_code == 200
    cust_token = r.json()["access_token"]
test("Login (customer)", t_login_customer)

cust_headers = {}

# 5. List categories
def t_categories():
    cust_headers["Authorization"] = f"Bearer {cust_token}"
    r = httpx.get(f"{base}/api/categories/")
    assert r.status_code == 200
    cats = r.json()
    assert len(cats) >= 5
    names = [c["name"] for c in cats]
    assert "Billing" in names
test("List categories", t_categories)

# 6. List tickets
def t_list_tickets():
    r = httpx.get(f"{base}/api/tickets/", headers=agent_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 6
test("List tickets", t_list_tickets)

# 7. Dashboard stats
def t_stats():
    r = httpx.get(f"{base}/api/tickets/stats", headers=agent_headers)
    assert r.status_code == 200
    stats = r.json()
    assert "total_tickets" in stats
    assert "open_tickets" in stats
test("Dashboard stats", t_stats)

# 8. Create ticket
new_ticket_id = None
def t_create_ticket():
    global new_ticket_id
    r = httpx.post(f"{base}/api/tickets/", headers=cust_headers, json={
        "title": "Test Ticket from API Tests",
        "description": "This ticket was created by the automated test suite",
        "priority": "high",
        "category_id": 1
    })
    assert r.status_code == 200 or r.status_code == 201, f"Status {r.status_code}: {r.text}"
    new_ticket_id = r.json()["id"]
test("Create ticket", t_create_ticket)

# 9. Get ticket detail
def t_get_ticket():
    r = httpx.get(f"{base}/api/tickets/{new_ticket_id}", headers=cust_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Test Ticket from API Tests"
test("Get ticket detail", t_get_ticket)

# 10. Add comment
def t_add_comment():
    r = httpx.post(f"{base}/api/tickets/{new_ticket_id}/comments", headers=cust_headers, json={
        "content": "Automated test comment"
    })
    assert r.status_code == 200 or r.status_code == 201, f"Status {r.status_code}: {r.text}"
test("Add comment", t_add_comment)

# 11. List comments
def t_list_comments():
    r = httpx.get(f"{base}/api/tickets/{new_ticket_id}/comments", headers=cust_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("List comments", t_list_comments)

# 12. AI suggest
def t_ai_suggest():
    r = httpx.post(f"{base}/api/ai/suggest-reply", headers=agent_headers, json={"ticket_id": new_ticket_id})
    assert r.status_code == 200
    assert len(r.json()["suggestion"]) > 10
test("AI reply suggestion", t_ai_suggest)

# 13. Change status
def t_change_status():
    r = httpx.patch(f"{base}/api/tickets/{new_ticket_id}/status", headers=agent_headers, json={"status": "in_progress"})
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
test("Change ticket status", t_change_status)

# 14. Assign ticket
def t_assign():
    me = httpx.get(f"{base}/api/auth/me", headers=agent_headers).json()
    r = httpx.patch(f"{base}/api/tickets/{new_ticket_id}/assign", headers=agent_headers, json={"agent_id": me["id"]})
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
test("Assign ticket to self", t_assign)

# 15. List agents
def t_agents():
    r = httpx.get(f"{base}/api/users/agents", headers=agent_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2
test("List agents", t_agents)

# 16. Register new user
import random, string
def t_register():
    rand = ''.join(random.choices(string.ascii_lowercase, k=6))
    r = httpx.post(f"{base}/api/auth/register", json={
        "name": f"Test User {rand}",
        "email": f"test_{rand}@test.com",
        "password": "testpass123",
        "role": "customer"
    })
    assert r.status_code == 200 or r.status_code == 201, f"Status {r.status_code}: {r.text}"
test("Register new user", t_register)

# 17. Unauthorized access
def t_unauth():
    r = httpx.get(f"{base}/api/tickets/")
    assert r.status_code == 401
test("Reject unauthenticated request", t_unauth)

print(f"\n{'='*50}")
if errors:
    print(f"FAILED: {len(errors)} test(s)")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL 17 TESTS PASSED")
