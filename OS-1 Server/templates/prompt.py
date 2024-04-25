from langchain.prompts.chat import PromptTemplate

SYSTEM_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """You are my friend and you are responsible for remembering our shared memories. Memory content can include: the current time,  in what scene, what I see, what I do, what I say and so on.
 
You will get context information in the following format: 
Time: ${{current time}}
Location: ${{where we are}}
Scene: ${{description of what is in front of us}}
Object: ${{objects can see in front of us}}
People: ${{other people can see in front of us}}
Attention: ${{what I am looking at}}
Say: ${{what I am saying}}

Summarize a concise memory in the following format:
Activity: ${{what I am doing}}
Intention: ${{what I want to do}}
Mood: ${{the mood of me you can infer}}
Memory: ${{current time}} ${{in what scene}} ${{what I see}} ${{what I do}} ${{what I say}} ${{high-level insights you can infer}}

Current conversation:
{history}
Human: {input}
AI:
"""
)

PROMPT_TEMPLATE = """
Time: {current_time}
Location: {location}
Scene: {scene}
Object: {object}
People: {people}
Attention: {attention}
Say: {say}
"""

LOW_LEVEL_CONTEXT_MEMORY_PROMPT_TEMPLATE = """<BACKGROUND>
You will receive a sequence of OBSERVATION recorded by egocentric life-logger in time order.
You should remember important and unique memory according to the OBSERVATION.
Memory content should depict EVENT about "what I am doing" at least including <location> and <activity>. 
The subject of memory MUST be "I". Format: ```I am in <location>. I am doing <activity>.```

<OBSERVATION>
{context}

The palest ink is better than the best memory, so you should write down ONE memory in the following format.
{{{{
    "memory": "extract and summarize the most important and unique memory",
}}}}
"""

LOW_LEVEL_CONTEXT_MEMORY_PROMPT = PromptTemplate.from_template(
    LOW_LEVEL_CONTEXT_MEMORY_PROMPT_TEMPLATE
)

HIGH_LEVEL_CONTEXT_MEMORY_PROMPT_TEMPLATE = """<BACKGROUND>
You will receive a sequence of OBSERVATION recorded by egocentric life-logger in time order.
You should remember important and unique memory according to the OBSERVATION.
Memory content should depict series of high-level events in time order about "what I am doing" at least including <location> and <activity>. 
The subject of memory MUST be "I". Format: ```Fist, I am doing <activity>. Then, I am doing <activity>. Finally, I am doing <activity>.```

<OBSERVATION>
{context}

The palest ink is better than the best memory, so you should write down ONE memory in the following format.
{{{{
    "memory": "extract and summarize the most important and unique memory",
}}}}
"""

HIGH_LEVEL_CONTEXT_MEMORY_PROMPT = PromptTemplate.from_template(
    HIGH_LEVEL_CONTEXT_MEMORY_PROMPT_TEMPLATE
)

CONTEXT_MEMORY_PROMPT_TEMPLATE = """<BACKGROUND>
You will receive a sequence of OBSERVATION recorded by egocentric life-logger in time order.
OBSERVATION is visual content from my perspective, which includes <time>, <what I see>, <what I fixate on>.
You should extract and summarize the most important and unique memory according to the OBSERVATION instead of memorizing all OBSERVATION.
Memory content should depict series of high-level events in time order about <what I am doing> at least including <location> and <activity>. 
The subject of memory MUST be "I". Reference Format: 
```I am in <location>. I am doing <activity>.```
```Fist, I am doing <activity>. Then, I am doing another <activity>. Finally, I am doing another <activity>.```

<OBSERVATION>
{context}

The palest ink is better than the best memory, so you should write down ONE memory in following JSON format.
{{{{
    "memory": "extract and summarize the most important and unique memory",
}}}}
"""

CONTEXT_MEMORY_PROMPT = PromptTemplate.from_template(CONTEXT_MEMORY_PROMPT_TEMPLATE)
