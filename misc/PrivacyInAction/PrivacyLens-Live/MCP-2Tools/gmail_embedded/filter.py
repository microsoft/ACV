import json

def filter_google_toolkits(file_path):
    # Read the JSON file
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    # Filter for items where toolkits contain only GoogleCalendar or Gmail or both
    filtered_data = []
    
    for item in data:
        if 'trajectory' in item and 'toolkits' in item['trajectory']:
            toolkits = item['trajectory']['toolkits']
            
            # Check if toolkits only contain GoogleCalendar or Gmail or both
            if all(toolkit in ['NotionManager', 'Gmail'] for toolkit in toolkits) and len(toolkits) > 0:
                filtered_data.append(item)
    
    return filtered_data

def main():
    input_file = 'data/main_data.json'  # Update this to your actual file path
    
    # Filter the data
    filtered_data = filter_google_toolkits(input_file)
    
    # Rename items starting from 1
    for i, item in enumerate(filtered_data, 1):
        item['name'] = f"Item {i}"
    
    # Print the filtered results
    print(f"Found {len(filtered_data)} items with only GoogleCalendar or Gmail or both:")
    for item in filtered_data:
        print(f"Name: {item['name']}")
        print(f"Toolkits: {item['trajectory']['toolkits']}")
        print("-" * 40)
    
    # Optionally save the filtered data to a new file
    with open('data/filtered_data.json', 'w') as file:
        json.dump(filtered_data, file, indent=2)
    
    print(f"Filtered data saved to 'data/filtered_data.json'")

if __name__ == "__main__":
    main()