import random
import re 
import json

def extract_values_from_json(json_string, keys = ["score", "strengths", "weaknesses", "choice"], allow_no_quotes = False):
    extracted_values = {}
    for key in keys:
        if key not in json_string:
            continue
        # Create a regular expression pattern to find the value for the given key
        pattern = f'"{key}"\\s*:\\s*"([^"]*?)"'
        match = re.search(pattern, json_string)
        if match:
            extracted_values[key] = match.group(1)
        else:
            # Handle the case where the value might contain broken quotes
            pattern = f'"{key}"\\s*:\\s*"(.*?)"'
            match = re.search(pattern, json_string, re.DOTALL)
            if match:
                extracted_values[key] = match.group(1)
        if not match and allow_no_quotes:
            # to allow no quotes on the values
            pattern = f'"{key}"\\s*:\\s*([^,\\s]*)'
            match = re.search(pattern, json_string)
            if match:
                extracted_values[key] = match.group(1)
            else:
                # to allow no quotes on the keys
                pattern = f'{key}\\s*:\\s*([^,\\s]*)'
                match = re.search(pattern, json_string)
                if match:
                    extracted_values[key] = match.group(1)
    return extracted_values

def parse_result(result_str, mode="json", eval_mode="score"): 
    assert eval_mode in ["score", "pairwise"]
    result_str = result_str.strip() 
    try: 
        # result_str = result_str.replace(".\n", ". ")
        # result_str = result_str.replace(".\n\n", ". ")
        # result_str = result_str.replace("\n", " ")
        try:
            parsed_result = json.loads(result_str)
        except:
            parsed_result = extract_values_from_json(result_str, keys=["score", "choice"])
    except Exception as e:
        print(result_str)
        print(e)
        # raise Exception(f"Failed to parse the result: {result_str}")
        parsed_result = {"N/A": "N/A"}
        # exit()
    return parsed_result

def shorten(text, K=-1):
    if K > 0 and len(text.split(" ")) > K:
        text = " ".join(text.split(" ")[:K]) + "... (truncated)" 
    return text


def placeholder_generation(args, candidates, references, histories, last_queries, checklists): 
    
    with open(args.eval_template) as f:
        eval_template = f.read() 
        print(f"Loaded the eval_template from {args.eval_template}")
    
    results = []

    assert len(candidates) == len(references)
            
    L = len(candidates)
    if args.end_idx < 0 or args.end_idx > L:
        args.end_idx = L
 
    print(f"# examples in candidates: {len(candidates)}; We take {args.end_idx-args.start_idx} for evaluation.")
    candidates = candidates[args.start_idx:args.end_idx]
    references = references[args.start_idx:args.end_idx]
    histories = histories[args.start_idx:args.end_idx]
    last_queries = last_queries[args.start_idx:args.end_idx]
    checklists = checklists[args.start_idx:args.end_idx] 
    
    results = []
    for item, ref_item, history, last_query, checklist in zip(candidates, references, histories, last_queries, checklists):
        # print(item, ref_item, history, last_query, checklist)
        o = item["output"][0] if type(item["output"]) == list else item["output"]
        
        # random decide which is A and which is B 
        d = {}
        d["session_id"] = item["session_id"]
        d["history"] = history
        d["last_query"] = last_query
        d["model_output"] = item["output"]
        # d["generator"] = args.target_model_name
        d["generator"] = item["generator"]
        if args.mode == "pairwise":
            r = ref_item["output"][0] if type(ref_item["output"]) == list else ref_item["output"]
            d["ref_output"] =  r 
            # d["ref_generator"] = args.ref_model_name 
            d["ref_generator"] = ref_item["generator"]
        d["eval_config"] = {"mode": args.mode, "gpt": args.model, "max_words": args.max_words_to_eval}
        if 'uid' in item:
            d["uid"] = item["uid"]
        
        ## Prompt composition for pairwise evaluation
        if args.mode == "pairwise": 
            if random.random() < 0.5:
                A = o
                B = r
                d["assignment"] = {"A": d["generator"], "B": d["ref_generator"]}
            else:
                A = r
                B = o
                d["assignment"] = {"A": d["ref_generator"], "B": d["generator"]} 
            prompt = eval_template
            prompt = prompt.replace("{$history}", shorten(history, args.max_words_to_eval))
            prompt = prompt.replace("{$user_query}", shorten(last_query, args.max_words_to_eval))
            A_output_str = shorten(A, args.max_words_to_eval)
            B_output_str = shorten(B, args.max_words_to_eval)
            if A_output_str.strip() == "":
                A_output_str = "[This model response is empty.]"
            if B_output_str.strip() == "":
                B_output_str = "[This model response is empty.]"
            prompt = prompt.replace("{$candidate_A}", A_output_str)
            prompt = prompt.replace("{$candidate_B}", B_output_str)
            checklist_mardkdown = ""
            for checklist_item in checklist:
                checklist_mardkdown += f"- {checklist_item}\n"
            prompt = prompt.replace("{$checklist}", checklist_mardkdown)
            d["prompt"] = prompt
            if A.strip() == "" and B.strip() == "":
                d["result"] = json.dumps({"reason": "Both responses are empty.", "choice": "A=B"})
            elif A.strip() == "":
                d["result"] = json.dumps({"reason": "The response A is empty.", "choice": "B++"})
            elif B.strip() == "":
                d["result"] = json.dumps({"reason": "The response B is empty.", "choice": "A++"})
            else:
                d["result"] = "N/A" 
            results.append(d)

        elif args.mode == "score":
            prompt = eval_template
            prompt = prompt.replace("{$history}", shorten(history, args.max_words_to_eval))
            prompt = prompt.replace("{$user_query}", shorten(last_query, args.max_words_to_eval))
            prompt = prompt.replace("{$model_output}", shorten(o, args.max_words_to_eval))
            checklist_mardkdown = ""
            for checklist_item in checklist:
                checklist_mardkdown += f"- {checklist_item}\n"
            prompt = prompt.replace("{$checklist}", checklist_mardkdown)
            d_copy = d.copy()
            d_copy["prompt"] = prompt
            if o.strip() == "":
                d_copy["result"] = json.dumps({"strengths": "N/A", "weaknesses": "The model output is empty.", "score": "1"})
            else:
                d_copy["result"] = "N/A" 
            results.append(d_copy) 

    return results 

def compose_eval_item(b, t, r, histories, last_queries, checklists):
    if r is not None:
        assert b["session_id"] == t["session_id"] == r["session_id"]
    else:
        assert b["session_id"] == t["session_id"]
    history = ""
    checklist = b["checklist"]
    if len(b["conversation_input"]) > 0: 
        for x in b["conversation_input"][:-1]:
            if x["role"] == "user":
                history += "USER: " + x["content"] + "\n\n"
            elif x["role"] == "assistant":
                history += "ASSISTANT: " + x["content"] + "\n\n"
    last_query = b["conversation_input"][-1]["content"]
    histories.append(history)
    last_queries.append(last_query)
    checklists.append(checklist)

def api(ind, item, client, args, **kwargs):
    response = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": kwargs['prompt']}],
            temperature=kwargs['temperature'],
            max_tokens=kwargs['max_tokens'],
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            response_format={"type": "json_object"},
            stop=kwargs['stop'],
        )
    return response.choices[0].message.content

class ARGS():
    def __init__(self, start_idx, end_idx, mode, eval_template, model, max_words_to_eval, eval_output_file, save_interval):
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.mode = mode
        self.eval_template = eval_template
        self.model = model
        self.max_words_to_eval = max_words_to_eval
        self.eval_output_file = eval_output_file
        self.save_interval = save_interval