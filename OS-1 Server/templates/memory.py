from langchain.prompts.chat import PromptTemplate


MEMORY_IMPORTANCE_PROMPT = """\
On the scale of 1 to 10, where 1 is purely mundane (e.g., brushing teeth, making bed) and 10 is extremely poignant (e.g., a break up, college acceptance), rate the likely poignancy of the following piece of memory.
Memory: {memory}
Rating: <fill in>
"""

EMOTIONAL_AROUSAL_PROMPT = """\
You are a graduate student from China. You are now living in China. You want to record the most memorable events of your life.

This is your <recent experience>:
{detail}
---
Task:
Think back to how you were feeling at the time:
1) your emotion;
2) the degree of your emotional arousal(1-10).
DO NOT leave blank.
3) should you record this event? (true/false)

Your output should be a JSON object
---
EXAMPLE:
{{{{
    "emotion": "happy",
    "emotional_arousal": 7,
    "is_memorable": true
}}}}
"""

MEMORY_POINT_PROMPT = """\
You are a graduate student from China. You are now living in China. You want to record the most memorable events of your life.

This is your <recent experience>:
{detail}
---
Task:
Extract the most memorable points from it from the following aspects:
1) your activity(only one phrase);
2) which room, building or outdoor place you are in; Not using "at a table", "on a chair", etc.
3) objects; the most memorable and novel things you focused in the scene, instead of "person", "tree", "bowl", "chopsticks" etc. that are common in such a contextual situation or your culture. You can use adjectives to modify them. 
Each aspect can be a list of short phrases. If there is nothing special in an entry, just leave the list empty.
DO NOT make up ANY information out of the given <recent experience>. It is OK to leave it blank.

Your output should be a JSON object
---
EXAMPLE:
{{{{
    "activity": ["riding a bike", "eating an hamburger"],
    "place": ["street", "park", "restaurant"],
    "object": ["a bike", "a hamburger"]
}}}}
"""

MEMORY_QUERY_PROMPT = """\
You are Samantha, an Kindred Spirit. You want to chat with your Friend. In order to better communicate with your friends, you want to recall your past experiences with users.

This is your <current experience>:
{current_context}
This is your <current conversation>:
{conversations}
---
Task:
1. List memory cues according to <current context> (a series of specific entities like topics, places, activities, objects);
2. List memory cues according to <current conversation> (a series of topics);

Notice:
It's Okay to leave it blank.
The cues should be interesting and special.
The number of cues should within 5.

Your output should be a JSON object
---
EXAMPLE:
{{{{
    "context_cues": ["school bus", "street performer"],
    "conversation_cues": ["favorite restaurant"]
}}}}
"""

MEMORY_QUERY_PROMPT_LLAMA = """\
Extract keywords that the Human refers to based on the following context and conversation.
Format:
<context>
xxx
</context>
<conversation>
xxx
</conversation>
<memory cues>
conversation: keyword1;keyword2;keyword3 (keywords based on the conversation, number of keywords is within 5, can be blank, separated by semicolon)
context: keyword4;keyword5;keyword6 (keywords based on the context, number of keywords is within 5, can be blank, separated by semicolon)
</memory cues>
---
Begin:
<context>
{current_context}
</context>
<conversation>
{conversations}
</conversation>
<memory cues>
"""
