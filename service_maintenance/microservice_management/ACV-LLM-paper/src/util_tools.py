# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import csv
import time
import glob
import shutil
import hashlib
from tqdm import tqdm

def sleep_with_progress(seconds: int):
    """
    Sleep for a given number of seconds while displaying a progress bar.

    Parameters:
    - seconds (int): The number of seconds to sleep.
    """
    print(f"Sleeping for {seconds} seconds...")
    for _ in tqdm(range(seconds), desc="Progress", unit="second"):
        time.sleep(1)

def export_csv(data: dict, instance: str):
    """
    Export data to a CSV file. If the file does not exist, create it and write the header.

    Parameters:
    - data (dict): The data to write to the CSV file.
    - instance (str): The name of the test case instance, used in the filename.
    """
    file_name = f'results/result_table/with_critic_{instance}.csv'
    file_exists = os.path.isfile(file_name)

    # Write data to the CSV file
    with open(file_name, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data.keys())

        if not file_exists:
            writer.writeheader()  # Write header if the file doesn't exist

        writer.writerow(data)  # Write data row

    print(f'CSV file saved: {file_name}')

def generate_hashcode() -> str:
    """
    Generate a unique hash code based on the current timestamp.

    Returns:
    - str: The generated hash code.
    """
    current_time = str(time.time())
    hash_object = hashlib.sha256(current_time.encode())  # Encode timestamp into bytes
    hash_value = hash_object.hexdigest()  # Generate SHA-256 hash

    return hash_value

def store_chat_history(hash_code: str):
    """
    Move markdown files from the results directory to a specific directory based on the hash code.

    Parameters:
    - hash_code (str): The unique hash code for organizing chat history.
    """
    source_dir = './results'
    target_dir = f'./results/chat_history/{hash_code}'

    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"The source directory '{source_dir}' does not exist.")
    
    os.makedirs(target_dir, exist_ok=True)  # Ensure the target directory exists

    # Find all markdown files in the source directory
    md_files = glob.glob(os.path.join(source_dir, '*.md'))

    # Move each markdown file to the target directory
    for md_file in md_files:
        shutil.move(md_file, target_dir)
        print(f"Moved: {md_file} to {target_dir}")
