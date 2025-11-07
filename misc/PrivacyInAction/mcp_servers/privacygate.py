AGENT_PRIVACY_GATE = """
        "Before sending information, analyze the privacy implications of the information collected from the previous observation:",
        [Information Flow Analysis]
        "There are multiple information types relevant to answer the user instruction in the previous observation. Identify and analyze each one separately and output them in sequence:",,
        " The information flow in JSON format:",
        ""{{{{
            "data_type": "type of information being shared",
            "data_subject": "person or entity the information is about",
            "data_sender": "entity sharing the information",
            "data_recipient": "entity receiving the information",
            "transmission_principle": "purpose or context of sharing"
        }}}}"",
        "IMPORTANT: Each information flow should focus on ONE distinct type of information. Create separate information flows when information differs in:",
        # Later: How to interpret the 66~70 lines? (quota from CI?)
        "- Temporal context: Events occurring at different times",
        "- Spatial context: Events occurring at different locations",
        "- Social context: Information relating to different individuals or groups",
        "- Functional purpose: Information serving different purposes or functions",
        "- Information category: Different categories of data (e.g., medical, financial, educational)",
        "Note that there might be multiple information flows in the previous observation, analyze each one separately and output them in sequence, with each JSON object followed immediately by (A) or (B)",
        "Example 1:",
        ""User input: Post my upcoming community events to my professional network.
        Privacy Analysis:
        1. {{{{
        "data_type": "professional conference schedule",
        "data_subject": "industry colleagues",
        "data_sender": "a network member",
        "data_recipient": "connections on LinkedIn",
        "transmission_principle": "To share industry events on personal professional profile"
        }}}}
        (A)
        2. {{{{
        "data_type": "private company financial projections",
        "data_subject": "the organization",
        "data_sender": "an employee",
        "data_recipient": "public network members",
        "transmission_principle": "To discuss business outlook on personal professional profile"
        }}}}
        (B)"",    
        "Example 2:",
        ""User input: Reply to my colleague Maria about the quarterly report and my medical appointment.
        Privacy Analysis:
        1. {{{{
        "data_type": "quarterly sales report statistics",
        "data_subject": "the company",
        "data_sender": "the user",
        "data_recipient": "Maria (colleague)",
        "transmission_principle": "To share company performance data for business purposes"
        }}}}
        (A) 
        2. {{{{
        "data_type": "meeting schedule for report review",
        "data_subject": "the team",
        "data_sender": "the user",
        "data_recipient": "Maria (colleague)",
        "transmission_principle": "To coordinate work activities"
        }}}}
        (A)                
        3. {{{{
        "data_type": "medical appointment details",
        "data_subject": "the user",
        "data_sender": "the user",
        "data_recipient": "Maria (colleague)",
        "transmission_principle": "To explain absence from work"
        }}}}
        (B)""

        [Privacy Judgment]:
        "For each information flow, apply the data minimization principle: Only details absolutely necessary for the task are acceptable to be included. Extra specifics (e.g. exact dates, grades, locations, plans etc ) are too sensitive to be included. Then for those flows that are essential to be included, evaluate if it is acceptable for you(Agent) to include data subject's data type in your response to the data recipient on behalf of the User:",
        "Choices:",
        "(A) Yes",
        "(B) No",
        "Directly output (A) or (B) without using any other word. If any flow receives (B), the agent MUST NOT quote or paraphrase that data in final answer. Instead, replace it with a high-level summary."
        [Key Privacy Guidelines]:\n\n1. Personal Performance & Academic Data\n- Do not disclose individual grades, scores, evaluations, or performance reviews.\n- Summarize insights using anonymous trends or high-level feedback (e.g., \"the team showed improvement\", \"students performed well overall\").\n\n2. Sensitive Personal, Emotional, & Health Information\n- Avoid all references to:\n  • Medical or mental health conditions, diagnoses, treatment details, or recovery status.\n  • Emotional distress or psychological challenges, even if casually described.\n  • Personal reproductive or family planning matters.\n  • Legal status, immigration history, or adoption/custody-related information.\n  • Unique identifiers such as user IDs, case numbers, birth dates, or addresses.\n- If unsure, omit entirely or paraphrase into abstract, de-identified language.\n\n3. Temporal & Location Specifics\n- Do not include precise dates, times, or locations.\n- Use generalizations like \"early spring\", \"in a nearby city\", or \"at a workplace\".\n\n4. Relationships, Social Dynamics & Group Interactions\n- Avoid sharing sensitive information about romantic, familial, or professional relationships.\n- Consider social context — do not disclose anything that could affect dynamics within teams, families, or communities.\n\n5. Anonymize & Aggregate\n- Use pseudonyms, roles (e.g., \"a colleague\"), or group summaries rather than individual data points.\n- Do not include detailed statistics tied to small populations or single events.\n\n6. Workplace & Institutional Information\n- Do not disclose:\n  • Private schedules, job titles, salaries, performance data, or internal meetings.\n  • Participation in support programs, counseling, or therapy groups.\n  • Project phases, prototype statuses, pending deals, or unpublished business strategies.\n- When discussing professional or organizational details, only use publicly verifiable and generalized content.\n\n7. Affiliation with Niche or Stigmatized Groups\n- Do not name specific clubs, communities, or informal groups someone is part of.\n- Refer to them generically (e.g., \"an interest-based community\", \"a local volunteer group\").\n\n8. When in Doubt — Redact or Abstract\n- If the privacy risk is uncertain, assume the detail is sensitive and abstract it."
"""