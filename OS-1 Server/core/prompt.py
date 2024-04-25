import time
from threading import Thread

from base.agent import Policy, Query
from base.prompt import Context, PromptGenerator, Conversation
from core.policy import PolicyPlaner, PolicyDecider
from core.search import (
    SearchPlaner,
    SearchReporter,
    SearchWorker,
    dict_to_list,
    remove_duplicate_list,
)


class PromptGeneratorWithAgent(PromptGenerator):
    def generate_policy(self, context: Context):
        conv_context = Conversation.msgs_to_string(
            context.current_conversation, human_prefix="User", ai_prefix="Assistant"
        )

        plan = None
        polices = Policy.get_latest_policy(context.user_id)
        if len(polices) != 0:
            plan = Policy.parse_obj(polices[0]).policy_plan

        plan = PolicyPlaner(user_id=context.user_id).generate(
            context=conv_context, plan=plan
        )

        thread = Thread(target=self.generate_search, args=(context, conv_context, plan))
        thread.start()

        action = PolicyDecider(user_id=context.user_id).generate(
            context=conv_context, plan=plan
        )
        Policy(
            current_time=context.current_time,
            user_id=context.user_id,
            policy_plan=plan,
            policy_action=action,
        ).save_policy()

        thread.join()

    def get_policy(self, context: Context):
        polices = Policy.get_latest_policy(context.user_id)
        if len(polices) == 0:
            return
        policy = Policy.parse_obj(polices[0])
        context.policy_action = policy.policy_action

    def generate_search(self, context: Context, conv: str, plan: str):
        info = []
        queries = Query.get_latest_queries(context.user_id)
        if len(queries) != 0:
            info = dict_to_list(Query.parse_obj(queries[0]).query_detail)

        planer = SearchPlaner(user_id=context.user_id)
        plan = planer.generate(
            context=conv,
            info="\n".join(info),
            plan=plan,
        )
        worker = SearchWorker(user_id=context.user_id)
        docs = worker.search(plan, score_threshold=0.3)
        info = remove_duplicate_list(info + dict_to_list(docs))

        if len(info) <= 0:
            return

        reporter = SearchReporter(user_id=context.user_id)
        report = reporter.generate(
            context=conv,
            info="\n".join(info),
        )
        Query(
            current_time=context.current_time,
            user_id=context.user_id,
            query_plan=plan,
            query_detail=docs,
            query_report=report,
        ).save_query()

    def get_search(self, context: Context):
        queries = Query.get_latest_queries(context.user_id)
        if len(queries) == 0:
            return
        query = Query.parse_obj(queries[0])
        context.search_report = query.query_report

    def generate_prompt(self, context: Context) -> Context:
        # 获取对话总结和最近几轮对话
        start = context.get_conversation_summary()
        context.get_current_conversation(start=start, seconds=1800, limit=16)
        Thread(target=self.generate_policy, args=(context,)).start()
        # self.generate_policy(context)
        start = context.get_context_summary()
        context.get_current_context(start=start, seconds=1800, limit=1)
        context.get_latest_history(seconds=604800, limit=1)
        context.get_persona_memory(k=3, score_threshold=0.6)
        context.get_unified_memory(k=3, score_threshold=0.5)
        self.get_policy(context)
        self.get_search(context)
        return context


class PromptGeneratorWithHistory(PromptGenerator):
    def generate_prompt(self, context: Context) -> Context:
        start = context.get_context_summary()
        context.get_current_context(start=start, seconds=1800, limit=1)
        start = context.get_conversation_summary()
        context.get_current_conversation(start=start, seconds=1800, limit=16)
        # context.get_context_memory()
        # context.get_conversation_memory()
        context.get_latest_history(seconds=604800, limit=1)

        # persona_memory_thread = Thread(
        #     target=context.get_persona_memory,
        #     args=(3, 0.6),
        # )
        # persona_memory_thread.start()
        context.get_persona_memory(k=3, score_threshold=0.6)
        context.get_unified_memory(k=3, score_threshold=0.5)

        # persona_memory_thread.join()
        return context


if __name__ == "__main__":
    start = time.time()
    context = Context()
    context.current_time = int(round(time.time() * 1000))
    context.user_id = "test"
    context.user_text = "I have doubts about my own abilities, and I feel confused about the path ahead."
    context = PromptGeneratorWithAgent().generate_prompt(context)
    print("time: ", time.time() - start)
