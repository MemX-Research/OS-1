from langchain.prompts import PromptTemplate

CONTEXT_EVENT_SUMMARY_PROMPT_TEMPLATE = """<BACKGROUND>
You will receive a sequence of CONTEXT recorded by egocentric life-logger in chronological order.
CONTEXT is visual content from my perspective, which includes <time>, <what I see>, <what I fixate on>.
You should extract and summarize the most important and actual event according to the CONTEXT.
EVENT content should depict about <what I am doing> at least including <location> and <activity>. 
The subject of memory MUST be "I". Reference Format: 
```I am in <location>. I am doing <activity>.```
```First, I am doing <activity>. Then, I am doing another <activity>. Finally, I am doing another <activity>.```

<CONTEXT>
{context}

The palest ink is better than the best memory, so you should write down ONE event in following JSON format.
{{{{
    "summary": "summarize the event without details",
    "detail": "depict the event with details"
}}}}
"""

CONTEXT_EVENT_SUMMARY_PROMPT = PromptTemplate.from_template(
    CONTEXT_EVENT_SUMMARY_PROMPT_TEMPLATE
)

CONTEXT_EVENT_CLUSTER_PROMPT_TEMPLATE = """<BACKGROUND>
You will receive a sequence of EVENT recorded by egocentric life-logger in chronological order.
EVENT is about <location> and <activity> from my perspective, which includes <temporal interval>, <event summary>, <event detail>.
You should merge similar events into one event and remove duplicate events. You should ignore the details of the event, as long as the <event summary> is similar, it is considered to be the same event.
The definition of similarity of events summary is, if they are completely different, the score is 0, if they are exactly the same, the score is 100. The higher your score on judging these events, the more similar they are. So if the score is equal or greater than 10, it means similar.
The subject of memory MUST be "I". Reference Format: 
```I am in <location>. I am doing <activity>.```
```First, I am doing <activity>. Then, I am doing another <activity>. Finally, I am doing another <activity>.```

<EVENTS>
{context}

Less is more, so you should merge events in following JSON format.
[
    {{{{
        "memory": "summarize the event without details",
        "detail": "depict the event with details"
    }}}}
]
"""

CONTEXT_EVENT_CLUSTER_PROMPT = PromptTemplate.from_template(
    CONTEXT_EVENT_CLUSTER_PROMPT_TEMPLATE
)

CONTEXT_EVENT_PROMPT_TEMPLATE = """<BACKGROUND>
You will receive a sequence of EVENT recorded by egocentric life-logger in chronological order.
EVENT is about <location> and <activity> from my perspective, which includes <temporal interval>, <event summary>, <event detail>.
You should merge similar events into one event and remove duplicate events. You should ignore the details of the event, as long as the <event summary> is similar, it is considered to be the same event.
The subject of memory MUST be "I". Reference Format: 
```I am in <location>. I am doing <activity>.```
```First, I am doing <activity>. Then, I am doing another <activity>. Finally, I am doing another <activity>.```

<EVENTS>
{context}

The palest ink is better than the best memory, so you should write down ONE event in following JSON format and ensure to include all detail information.
{{{{
    "summary": "depict the events without details",
    "detail": "depict the events with all details"
}}}}
"""

CONTEXT_EVENT_PROMPT = PromptTemplate.from_template(CONTEXT_EVENT_PROMPT_TEMPLATE)
