import os
import csv
import time
import glob
import shutil
import hashlib
from tqdm import tqdm

def sleep_with_progress(seconds):
    print(f"Sleeping for {seconds} seconds...")

    for _ in tqdm(range(seconds), desc="Progress", unit="second"):
        time.sleep(1)

def export_csv(data, instance):
    file_name = f'results/result_table/with_critic_{instance}.csv'

    file_exists = os.path.isfile(file_name)

    with open(file_name, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data.keys())

        if not file_exists:
            writer.writeheader()

        writer.writerow(data)

    print(f'CSV file saved: {file_name}')

def generate_hashcode():
    current_time = str(time.time())
    hash_object = hashlib.sha256(current_time.encode())  # 将时间戳编码为字节
    hash_value = hash_object.hexdigest() 

    return hash_value

def store_chat_history(hash_code):
    source_dir = './results'
    target_dir = f'./results/chat_history/{hash_code}'
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"The source directory '{source_dir}' does not exist.")
    
    os.makedirs(target_dir, exist_ok=True)
    md_files = glob.glob(os.path.join(source_dir, '*.md'))
    
    # Move each markdown file to the target directory
    for md_file in md_files:
        shutil.move(md_file, target_dir)
        print(f"Moved: {md_file} to {target_dir}")