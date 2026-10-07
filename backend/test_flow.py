import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)

# 1. Health
h = c.get("/api/health")
print("1. Health check:", h.json())

# 2. Register / Login
auth_data = {"email": "student_test@codemate.ai", "password": "password123"}
reg = c.post("/api/auth/register", json={"name": "Test Student", "confirm_password": "password123", **auth_data})
if reg.status_code == 200:
    token = reg.json().get("access_token")
else:
    login = c.post("/api/auth/login", json=auth_data)
    token = login.json().get("access_token")
print("2. Token acquired:", token[:15] + "...")

headers = {"Authorization": f"Bearer {token}"}

# 3. Upload a sample C file
sample_code = """#include <stdio.h>
int main() {
    int n, temp, reverse = 0, rem;
    printf("Enter a number: ");
    scanf("%d", &n);
    temp = n;
    while (temp != 0) {
        rem = temp % 10;
        reverse = reverse * 10 + rem;
        temp = temp / 10;
    }
    if (reverse == n) {
        printf("%d is a Palindrome Number\\n", n);
    } else {
        printf("%d is NOT a Palindrome Number\\n", n);
    }
    return 0;
}
"""
files = {"file": ("palindrome.c", sample_code.encode("utf-8"), "text/plain")}
up = c.post("/api/projects/upload", files=files, data={"technology": "C"}, headers=headers)
print("3. Upload status:", up.status_code, "Project:", up.json().get("name"), "Tech:", up.json().get("technology"))
proj_id = up.json().get("id")

# 4. Ask about working output
chat_payload = {
    "project_id": proj_id,
    "question": "Show the terminal compilation, execution steps, and sample working output for this code",
    "knowledge_level": 20,
    "language": "English",
    "format": "block_by_block"
}
ask = c.post("/api/chat/ask", json=chat_payload, headers=headers)
print("4. Chat / Ask status:", ask.status_code)
ans = ask.json().get("answer", "")
print("=" * 60)
print("SAMPLE ANSWER GENERATED:")
print("=" * 60)
print(ans)
print("=" * 60)
