from langchain.prompts import PromptTemplate

LOCATION_PROMPT = """Where is the location"""
OBJECT_PROMPT = """Tell me the things in this picture in detail: They are"""
PEOPLE_PROMPT = (
    """If there is anyone, answer who is there. If there is no one, answer none."""
)

ACTIVITY_PROMPT_TEMPLATE = """<BACKGROUND>
You are an Egocentric Video Captioner, you can understand a video and infer my ACTIVITY. You will receive a sequence of frame captions within a minute.

<OBJECTIVE>
Generate a description of "what I am doing".

<NOTICE>
The captions are from a Visual Language Model, so they may be not correct.
The subject of the "activity" sentence MUST be "I".

<INPUT>
<FRAME CAPTIONS>
{frames}
</FRAME CAPTIONS>
</INPUT>


You should only respond in JSON format as described below
{{{{
    "location": "where I am",
    "activity": "what I am doing",
    "summary": "the context about me"
}}}}
"""

ACTIVITY_PROMPT = PromptTemplate.from_template(ACTIVITY_PROMPT_TEMPLATE)

EPISODIC_PROMPT = """\
You are a human behaviorist. You can infer the user's behavior, location, and emotion at this point in time from the user's previous conversation and the scene in which that conversation took place.

This is the scenario that the User sees:
{scene}

This is a recent conversation between the User and their friend Samantha:
{conversation}

Output in a JSON object like:
{{{{
    "activity": "e.g. User is likely doing...",
    "location": "e.g. in a cafeteria",
    "emotion": "e.g. happy"
}}}}
"""
