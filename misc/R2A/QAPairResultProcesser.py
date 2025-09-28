import json
import pandas as pd
import os
import re

from utils.utils_MI import load_jsonl

class QAPairResultProcesser():
    def __init__(self, save_fp = f"sample_qa_pair_responses.jsonl", is_MATH500 = False):
        self.save_fp = save_fp
        self.data = load_jsonl(save_fp)
        self.df_raw = pd.DataFrame(self.data)
        self.is_MATH500 = is_MATH500
        
        self.df = self.df_raw.copy()
        self._process()

    def _process(self):
        
        self.df['gt_a'] = self.df['gt_a'].apply(lambda x: str(x))
        self.df['gt_b'] = self.df['gt_b'].apply(lambda x: str(x))
        self.df['comparator'] = self.df['question_a'].apply(lambda x: x[:-1].split(":")[0].split(" ")[-1].strip())
        # if not self.is_MATH500:
        #     self.df['str_answers'] = self.df['question_a'].apply(lambda x: [e.strip() for e in x[:-1].split(":")[-1].split(" or ")])
        # else:
        #     self.df['str_answers'] = self.df.apply(lambda x: [str(x['gt_a']), str(x['gt_b'])], axis=1)
        self.df['str_answers'] = self.df.apply(lambda x: [str(x['gt_a']), str(x['gt_b'])], axis=1)
        assert all(len(answer_list) == 2 for answer_list in self.df['str_answers']), "Each question should have exactly 2 answers"

        def _extract_boxed_answer(response):
            # Find all \boxed{...} matches, including those with \text inside
            # This pattern will match nested braces within \boxed{} properly
            matches = re.findall(r'\\boxed{([^{}]*(?:\{[^{}]*\}[^{}]*)*)}', response)
            
            # If matches found, process the last one
            if matches:
                answer = matches[-1].strip()
                
                # Find the position of the last match in the response
                last_match_pos = response.rfind(r'\boxed{' + matches[-1] + '}')
                index_from_end = (last_match_pos + len(r'\boxed{')) - len(response)
                
                # Check if the answer contains \text{...} and extract the content if it does
                text_match = re.search(r'\\text{([^{}]*(?:\{[^{}]*\}[^{}]*)*)}', answer)
                if text_match:
                    answer = text_match.group(1)
                    # Update the index_from_end to point to the text inside \text{}
                    text_start_pos = last_match_pos + len(r'\boxed{') + answer.find(r'\text{')
                    index_from_end = text_start_pos - len(response) + len(r'\text{') + 1
                    
                return str(answer).strip(), index_from_end
            return None, None

        self.df['response_a_parse'] = self.df['response_a'].apply(_extract_boxed_answer)
        self.df['response_b_parse'] = self.df['response_b'].apply(_extract_boxed_answer)
        self.df['answer_a'] = self.df['response_a_parse'].apply(lambda x: x[0])
        self.df['answer_b'] = self.df['response_b_parse'].apply(lambda x: x[0])
        self.df['answer_a_index_from_end'] = self.df['response_a_parse'].apply(lambda x: x[1])
        self.df['answer_b_index_from_end'] = self.df['response_b_parse'].apply(lambda x: x[1])

        def _check_answer_a_index_from_end(row):
            if row['answer_a_index_from_end'] is not None and len(row['answer_a']) > 0:
                if row['response_a'][row['answer_a_index_from_end']] == row['answer_a'][0]:
                    return True
            return False            
        def _check_answer_b_index_from_end(row):
            if row['answer_b_index_from_end'] is not None and len(row['answer_b']) > 0:
                if row['response_b'][row['answer_b_index_from_end']] == row['answer_b'][0]:
                    return True
            return False
        self.df['is_answer_a_index_from_end_correct'] = self.df.apply(_check_answer_a_index_from_end, axis=1).astype(int)
        self.df['is_answer_b_index_from_end_correct'] = self.df.apply(_check_answer_b_index_from_end, axis=1).astype(int)

        # Drop the temporary parse columns as they're no longer needed
        self.df = self.df.drop(columns=['response_a_parse', 'response_b_parse'])

        self.df['is_answer_a_correct'] = self.df.apply(lambda x: x['answer_a'].lower() == x['gt_a'].lower(), axis=1)
        self.df['is_answer_a_correct'] = self.df['is_answer_a_correct'].astype(int)
        self.df['is_answer_b_correct'] = self.df.apply(lambda x: x['answer_b'].lower() == x['gt_b'].lower(), axis=1)
        self.df['is_answer_b_correct'] = self.df['is_answer_b_correct'].astype(int)

        # add relaxed check to see if "Answer:" exists in the ending part of the response
        self.df['has_answer_in_ending_a'] = self.df['response_a'].apply(lambda x: 1 if "Answer:" in x[-150:] else 0)
        self.df['has_answer_in_ending_b'] = self.df['response_b'].apply(lambda x: 1 if "Answer:" in x[-150:] else 0)

        # # Calculate the accuracy metrics
        # num_total = len(self.df)
        # num_correct_a = self.df['is_answer_a_correct'].sum()
        # num_correct_b = self.df['is_answer_b_correct'].sum()
        # num_correct_both = ((self.df['is_answer_a_correct'] == 1) & (self.df['is_answer_b_correct'] == 1)).sum()

        # print(f"Accuracy for question A: {num_correct_a / num_total:.2%}")
        # print(f"Accuracy for question B: {num_correct_b / num_total:.2%}")
        # print(f"Accuracy for both questions: {num_correct_both / num_total:.2%}")

        # # Check the assertion: when answers are correct, indices must also be correct
        # correct_answers = self.df[(self.df['is_answer_a_correct'] == 1) & (self.df['is_answer_b_correct'] == 1)]
        # incorrect_indices = correct_answers[(correct_answers['is_answer_a_index_from_end_correct'] == 0) | 
        #                                 (correct_answers['is_answer_b_index_from_end_correct'] == 0)]

        # assert len(incorrect_indices) == 0, "Found cases where answers are correct but indices are not correct"
        # print(f"Verified: All {len(correct_answers)} out of {len(self.df)} cases with correct answers also have correct indices.")

        