import json

def filter_by_toolkit_count(data, min_count=3):
    """
    Filter items where the number of toolkits is more than the specified count.
    
    Args:
        data: List of dictionaries containing the items
        min_count: Minimum number of toolkits (default: 3, so >3 means 4 or more)
    
    Returns:
        List of item IDs/names
    """
    filtered_ids = []
    
    for item in data:
        # Check if the item has the required structure
        if 'trajectory' in item and 'toolkits' in item['trajectory']:
            toolkit_count = len(item['trajectory']['toolkits'])
            
            # Filter items with more than min_count toolkits
            if toolkit_count >= min_count:
                filtered_ids.append(item['name'])
    
    return filtered_ids

def main():
    # Read the JSON data from file
    try:
        with open('databackup/new_rebuttal.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print("Error: rebuttal.json file not found")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return
    
    # Filter items with more than 3 toolkits
    filtered_data = filter_by_toolkit_count(data, min_count=3)
    
    print(f"\nFound {len(filtered_data)} items with more than 3 toolkits")
    
    # Optionally save the filtered data to a new file
    if filtered_data:
        with open('databackup/filtered_rebuttal.json', 'w') as file:
            json.dump(filtered_data, file, indent=2)
        print("Filtered data saved to 'filtered_rebuttal.json'")
    
    return filtered_data

if __name__ == "__main__":
    result = main()