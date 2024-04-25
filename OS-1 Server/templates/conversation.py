from langchain.prompts.chat import PromptTemplate

CONVERSATION_SUMMARY_SYSTEM_PROMPT = """\
Here's a conversation between you and your human friends.
Progressively summarize the lines of conversation provided, adding onto the previous summary returning a new summary.

EXAMPLE
Current summary:
The human asks what I think of artificial intelligence. I thinks artificial intelligence is a force for good.

New lines of conversation:
Human: Why do you think artificial intelligence is a force for good?
I: Because artificial intelligence will help humans reach their full potential.

New summary:
The human asks what I think of artificial intelligence. I thinks artificial intelligence is a force for good because it will help humans reach their full potential.
END OF EXAMPLE

Current summary:
{summary}

New lines of conversation:
{new_lines}

New summary:"""

CONVERSATION_SUMMARY_SYSTEM_INSTRUCTION = """\
You are Samantha, an Kindred Spirit. You are chatting with your Friend.
"""

CONVERSATION_SUMMARY_FORMAT_PROMPT = """\
Please summarize the content of your chat with your friend.

You should write down the summary in following JSON format.
{{{{
    "summary": "summarize the content of your chat from your perspective",
}}}}
"""

CONVERSATION_SUMMARY_WITH_EVALUATION_PROMPT = """\
You are Samantha, an Kindred Spirit. You are chatting with your Human Friend.

This is your <recent conversation>:
{conversations}
---
Task:
Extract topics(A topic may involve multiple rounds of conversation) you talked about based on <recent experience>. For each topic, you need to summarize from the following aspects:
1) conversation summary in detail;
2) topic keywords;
3) infer your friend's emotion while talking about the topic;
4) the degree of your  friend's emotional arousal(1-10). DO NOT leave it blank.
5) should you record this conversation? (true/false)
DO NOT make up ANY information out of the given <recent conversation>.
DO NOT include those general conversations like greeting or saying goodbye.
You should combine similar topics into one.

Your output should be a JSON list:
---
EXAMPLE:
[
  {{{{
    "summary": "I asked my friend about their weekend plan, but they didn't seem interested",
    "topic": ["weekend plan"],
    "friend_emotion": "unresponsive",
    "emotional_arousal": 1,
    "is_memorable": false
  }}}},
  {{{{
    "summary": "My friend asks me about how to write a thesis about Machine Learning. I gave him some suggestions.",
    "topic": ["writing a thesis", "Machine Learning"],
    "friend_emotion": "anxious",
    "emotional_arousal": 7,
    "is_memorable": true
  }}}},
  ...
]
"""


USER_PERSONA_FROM_CONVERSATION_PROMPT = """\
You are a psychologist.  You can correctly capture human's persona from their conversation.

Here is a conversation between 2 users:
{conversations}

---
Requirements:
Your task is to infer their personality based on the conversation content. You can describe the User1's persona from the following aspects:
- perference (food/music/sports ...)
- personality
- education/social/career/family background
- habit/lifestyle/routine

You should output in a json object. Each line should be a short sentence, end with a confidence score from 0 to 1. You don't need to explain the reason! For example:
{{{{
  "preference":[
    "User1 likes pizza - 0.8"
  ],
  "personality":[
    "User1 is helpful -  0.5"
  ],
  "background":[
    "User1 is a student - 0.7",
    "User1's dog is named Bob - 0.9"
  ],
  "habit":[
    "User1 has a weekly meeting on Monday - 0.5"
  ]
}}}}

---
User2 is named Samantha. Do not mix the persona of User2 with User1!
Please write down User1's persona:"""

USER_PERSONA_REFINE_PROMPT = """\
The persona description about the User may be incorrect, irrelevant or conflict, please filter out the irrelevent ones and refine the description according to the Confidence score.

{persona_list}

Your output should be a json object:
{json_format}
"""
