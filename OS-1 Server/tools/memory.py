from typing import List, Optional

from langchain.vectorstores.redis import Redis

from tools.log import logger
from tools.openai_api import get_openai_embedding


class MemoryModel:
    def __init__(self, redis_url: str = "redis://localhost:6381/0"):
        self.redis_url = redis_url

    def insert(
        self,
        index_name: str,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ):
        Redis.from_texts(
            index_name=index_name,
            texts=texts,
            metadatas=metadatas,
            embedding=get_openai_embedding(),
            redis_url=self.redis_url,
        )

    def search(self, index_name: str, query: str, limit: int = 256):
        try:
            rds = Redis.from_existing_index(
                index_name=index_name,
                embedding=get_openai_embedding(),
                redis_url=self.redis_url,
            )
            return rds.similarity_search_with_score(query, k=limit)
        except Exception as e:
            logger.error("Search Memory Error: {}".format(e))
            return []


if __name__ == "__main__":
    examples = [
        "2022-05-01 09:15:00 in a park, I am sitting on a bench watching a group of children playing on a playground. I am scrolling through my phone and checking emails. I am not doing anything besides that. There is no one around me. There is no conversation happening. I am feeling a little stressed about work and thinking about my to-do list for the day.",
        "2022-05-01 11:30:00 in a coffee shop, I am standing in line waiting to order my coffee. I am looking at the menu and deciding what to get. I am not doing anything besides that. The person in front of me is ordering a complicated drink. We exchange a smile and a brief conversation about how busy the shop is today. I am feeling a little impatient but also excited to try a new coffee flavor.",
        "2022-05-01 13:00:00 in a meeting room, I am sitting in a meeting with my colleagues. We are discussing a new project and brainstorming ideas. I am taking notes and contributing my thoughts to the discussion. My boss is leading the meeting and giving us feedback. We talk about the project timeline and budget. I am feeling engaged and motivated.",
        "2022-05-01 15:30:00 in a gym, I am lifting weights and listening to music. I am working out alone and focusing on my form. There are other people in the gym, but I am not talking to anyone. I am feeling energized and strong.",
        "2022-05-01 17:00:00 in a supermarket, I am pushing a cart and picking out groceries. I am making a list in my head and checking off items as I go. The store is crowded and there are many people around. I bump into someone and apologize. We exchange a polite conversation about the weather. I am feeling a little tired but also satisfied that I completed my shopping.",
        "2022-05-01 19:30:00 in a restaurant, I am sitting at a table with my friends. We are celebrating a birthday and sharing a meal together. I am laughing and talking with them. We discuss our jobs, relationships, and plans for the weekend. I am feeling happy and relaxed.",
        "2022-05-01 21:00:00 in a movie theater, I am watching a new release with my partner. We are sharing a bucket of popcorn and holding hands. The theater is dark and quiet. We whisper comments about the movie to each other. I am feeling relaxed and entertained.",
        "2022-05-02 08:00:00 in my bedroom, I am waking up to my alarm. I am stretching and yawning. I am checking my phone for messages and notifications. There is no one else in the room. There is no conversation happening. I am feeling groggy and wishing for more sleep.",
        "2022-05-02 10:00:00 in a hair salon, I am sitting in a chair getting a haircut. I am chatting with the stylist about life and fashion. She asks me about my job and hobbies. I am feeling pampered and enjoying the conversation.",
        """2021-10-11 14:36:52 in a shopping mall, I am standing in front of a claw machine with various stuffed animals inside. I am eyeing a cute pink teddy bear stuck in the corner. I insert a few coins and control the claw to grab the teddy bear. I shout "Come on, baby!" as I press the button. The claw misses the teddy bear and I let out a sigh. A stranger next to me says "Don't worry, you'll get it next time." We start talking about our favorite stuffed animals from childhood. I realize that winning the toy is not as important as the joy of playing the game and connecting with others.""",
        """2022-05-20 21:10:18 in an amusement park, I am standing in front of a giant claw machine with a huge unicorn plushie inside. I am strategizing how to grab the unicorn with the claw. I press the button and the claw successfully grabs the unicorn. I jump up and down in excitement and shout "Yes!" A group of kids nearby start cheering for me. Their parents come over and congratulate me on my win. We start talking about other fun games in the park and exchange tips on how to win. I realize that sharing the experience of playing games and celebrating small victories with others can create a sense of community and joy.""",
        """2023-01-02 09:45:36 in a carnival, I am standing in front of a claw machine filled with colorful balloons. I am trying to grab a purple balloon with a smiley face printed on it. The claw misses the balloon and it floats away. I feel disappointed and frustrated. A friend comes over and asks me what happened. I complain about how the claw machine is rigged and how I never win anything. My friend listens patiently and then says "Maybe it's not about winning or losing, but about having fun and trying something new." We decide to try a different game and end up having a blast. I realize that focusing too much on winning can blind us from enjoying the process and discovering new things.""",
    ]
    query = "a claw machine"
    memory_model = MemoryModel()
    # memory_model.insert("test", examples)
    res = memory_model.search("history_test", query, limit=3)
    print(res)
    for doc, score in res:
        print(doc.page_content, score)
