D_MODEL_PAIR = {
    'R1-Llama-8B': ('llama-8B-withR', 'llama-8B-withoutR'),
    'R1-Qwen-7B': ('qwen-7B-withR', 'qwen-7B-withoutR'),
    'R1-Qwen-1.5B': ('qwen-1p5B-withR', 'qwen-1p5B-withoutR'),
    'R1-Full': ('r1-full-withR', 'r1-full-withoutR')
}

D_MODEL_ALIAS_PATH = {
    'llama-8B': r"deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    'qwen-7B': r"deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    'qwen-1p5B': r"deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
}

D_MODEL_ALIAS_LABEL_MAPPING = {
    'llama-8B': 'R1-Llama-8B',
    'qwen-7B': 'R1-Qwen-7B',
    'qwen-1p5B': 'R1-Qwen-1.5B'
}

D_TOP_RETRIEVAL_HEADS = {
    'qwen-1p5B': [[[19, 5], 0.87], [[14, 3], 0.8], [[19, 3], 0.78], [[23, 2], 0.72], [[23, 4], 0.58], [[14, 5], 0.55], [[23, 0], 0.55], [[23, 1], 0.55], [[19, 1], 0.39], [[14, 4], 0.38]], # [[[layer_index, head_indx], score], ...]
    'qwen-7B': [[[22, 3], 0.83], [[22, 4], 0.67], [[5, 19], 0.5], [[22, 1], 0.45], [[23, 11], 0.45], [[14, 4], 0.43], [[14, 0], 0.42], [[22, 5], 0.39], [[17, 8], 0.39], [[14, 5], 0.39]],
    'llama-8B': [[[15, 30], 0.82], [[2, 21], 0.55], [[16, 1], 0.45], [[5, 8], 0.39], [[8, 1], 0.39], [[5, 10], 0.38], [[24, 27], 0.35], [[20, 14], 0.34], [[10, 14], 0.31], [[16, 20], 0.31]],
}

D_TOP_INDUCTION_HEADS = {
    'llama-8B': [(2, 22), (5, 11), (15, 30), (16, 20), (10, 14), (18, 30), (15, 28), (16, 2), (2, 26), (29, 21)],
    'qwen-7B': [(14, 6), (22, 3), (2, 26), (17, 8), (22, 2), (17, 13), (14, 2), (5, 19), (7, 6), (5, 18)],
    'qwen-1p5B': [(2, 3), (14, 3), (19, 3), (14, 0), (23, 4), (23, 0), (8, 7), (14, 1), (2, 5), (19, 1)]
}

D_TOP_RFHS_BY_LAYER_HEAD = {
    "llama-8B": [(8, 11), (10, 31), (0, 22), (13, 6), (16, 1), (13, 18), (13, 5), (8, 9), (13, 4), (8, 1)],
    "qwen-7B": [(16, 0), (19, 15), (14, 7), (1, 1), (17, 18), (22, 7), (17, 19), (17, 14), (16, 14), (14, 0)],
    "qwen-1p5B": [(16, 2), (1, 5), (19, 1), (12, 1), (16, 11), (23, 2), (14, 3), (19, 5), (20, 9), (16, 0)]
}

D_MODEL_SAMPLE_RFH_LOWER_LAYER = {
    'llama-8B': [[0, 22]],
    'qwen-7B': [[1, 1]],
    'qwen-1p5B': [[1, 5]]
}

D_MODEL_SAMPLE_RFH_MIDDLE_LAYER = {
    'llama-8B': [[10, 31]],
    'qwen-7B': [[14, 7]],
    'qwen-1p5B': [[16, 2]]
}

D_MODEL_SAMPLE_CASES = {
    'llama-8B': ["test/algebra/2476.json", "test/precalculus/541.json", "test/counting_and_probability/765.json"],
    'qwen-7B': ["test/prealgebra/1865.json", "test/algebra/2159.json", "test/intermediate_algebra/1898.json"],
    'qwen-1p5B': ["test/algebra/1547.json", "test/geometry/538.json", "test/algebra/893.json"]
}

# shorter alias name for the sample cases
D_MODEL_SAMPLE_CASES_ALIAS = {
    'llama-8B': ["test/algebra/2476.json", "test/precalculus/541.json", "test/count_&_prob/765.json"],
    'qwen-7B': ["test/prealgebra/1865.json", "test/algebra/2159.json", "test/mid_algebra/1898.json"],
    'qwen-1p5B': ["test/algebra/1547.json", "test/geometry/538.json", "test/algebra/893.json"]
}

D_MODEL_SAMPLE_CASES_FOR_COLORED_TOKENS = {
    'llama-8B': [
        # "test/prealgebra/505.json", # tok length: 742, "wait" is used for double check and "wait" results are used in the answer
        # "test/precalculus/819.json", # tok length: 842, short answer and answer content seems to picked from the reasoning
        # "test/prealgebra/1922.json", # tok length: 940, content after "wait" is not used for the answer
        # "test/prealgebra/1761.json", # tok length: 995
        # "test/algebra/2476.json", # model_pair_comp = -1
        # "test/counting_and_probability/765.json", # model_pair_comp = 1
        "test/precalculus/541.json", # model_pair_comp = 0
        # "test/algebra/2199.json", # model_pair_comp = 0
    ],
    'qwen-7B': [
        # "test/prealgebra/2019.json", # model_pair_comp = 0
        # "test/algebra/2159.json", # model_pair_comp = 0
        # "test/algebra/1457.json", # model_pair_comp = 0
        # "test/intermediate_algebra/1210.json", # model_pair_comp = 1
        # "test/intermediate_algebra/1898.json", # model_pair_comp = 1
        "test/prealgebra/1865.json", # model_pair_comp = -1
    ],
    'qwen-1p5B': [
        "test/algebra/1547.json", # model_pair_comp = -1
        # "test/algebra/2743.json", # model_pair_comp = 0
        # "test/geometry/538.json", # model_pair_comp = 0
        # "test/algebra/893.json", # model_pair_comp = 1
    ]
}
