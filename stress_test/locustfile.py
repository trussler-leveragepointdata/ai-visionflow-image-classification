from pathlib import Path
from typing import Optional

import requests
from locust import HttpUser, between, task

API_BASE_URL = "http://localhost:8000"
DOG_IMAGE = (Path(__file__).parent / "dog.jpeg").read_bytes()


def login(username: str, password: str) -> Optional[str]:
    """This function calls the login endpoint of the API to authenticate the user and get a token.

    Args:
        username (str): email of the user
        password (str): password of the user

    Returns:
        Optional[str]: token if login is successful, None otherwise
    """
    url = f"{API_BASE_URL}/login"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "",
        "username": username,
        "password": password,
        "scope": "",
        "client_id": "",
        "client_secret": "",
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


class APIUser(HttpUser):
    host = API_BASE_URL
    wait_time = between(1, 5)

    def on_start(self) -> None:
        token = login("admin@example.com", "admin")
        self.auth_headers = {"Authorization": f"Bearer {token}"}

    @task(1)
    def index(self) -> None:
        self.client.get("/", name="index")

    @task(1)
    def predict(self) -> None:
        self.client.post(
            "/model/predict",
            headers=self.auth_headers,
            files={"file": ("dog.jpeg", DOG_IMAGE, "image/jpeg")},
        )
