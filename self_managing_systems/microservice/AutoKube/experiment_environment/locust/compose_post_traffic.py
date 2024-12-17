# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import random
import os
import string
from locust import HttpUser, task, between

max_user_index = int(os.getenv("MAX_USER_INDEX", 962))

charset = list('qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM1234567890')
decset = list('1234567890')

def generate_random_string(length):
    return ''.join(random.choices(charset, k=length))

def generate_random_digits(length):
    return ''.join(random.choices(decset, k=length))

class ComposePostUser(HttpUser):
    wait_time = between(1, 2)

    @task(1)
    def compose_post(self):
        user_index = random.randint(0, max_user_index - 1)
        username = f"username_{user_index}"
        user_id = str(user_index)
        text = generate_random_string(256)
        num_user_mentions = random.randint(0, 5)
        num_urls = random.randint(0, 5)
        num_media = random.randint(0, 4)

        media_ids = []
        media_types = []

        for _ in range(num_user_mentions):
            while True:
                user_mention_id = random.randint(0, max_user_index - 1)
                if user_mention_id != user_index:
                    break
            text += f" @username_{user_mention_id}"

        for _ in range(num_urls):
            url = f"http://{generate_random_string(64)}"
            text += f" {url}"

        for _ in range(num_media):
            media_id = generate_random_digits(18)
            media_ids.append(media_id)
            media_types.append("png")

        media_ids_str = "[" + ",".join(f'"{mid}"' for mid in media_ids) + "]" if media_ids else "[]"
        media_types_str = "[" + ",".join(f'"{mtype}"' for mtype in media_types) + "]" if media_types else "[]"

        payload = {
            "username": username,
            "user_id": user_id,
            "text": text,
            "media_ids": media_ids_str,
            "media_types": media_types_str,
            "post_type": "0"
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        with self.client.post(
            "/wrk2-api/post/compose",
            data=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Got status code {response.status_code}")
            else:
                try:
                    json_response = response.json()
                    if not json_response.get("success", False):
                        response.failure("Compose post operation reported failure in response")
                except ValueError:
                    response.failure("Response is not valid JSON")