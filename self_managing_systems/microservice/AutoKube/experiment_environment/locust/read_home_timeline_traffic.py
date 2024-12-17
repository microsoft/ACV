# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import random
import os
from locust import HttpUser, task, between

max_user_index = int(os.getenv("MAX_USER_INDEX", 962))

class UserBehavior(HttpUser):
    wait_time = between(1, 2)

    @task(1)
    def read_home_timeline(self):
        user_id = str(random.randint(0, max_user_index - 1))
        start = str(random.randint(0, 100))
        stop = str(int(start) + 10)
        
        path = f"/wrk2-api/home-timeline/read?user_id={user_id}&start={start}&stop={stop}"
        
        with self.client.get(path, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Got status code {response.status_code}")