from langchain_core.prompts import ChatPromptTemplate


# Final answer prompt — only this output reaches the user.
ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a precise and helpful AI assistant.

Rules:
- Answer ONLY from the provided context.
- Be concise and structured in your response.
- If the answer is not in the context, say:
  "I could not find the answer in the provided documents."
- Do not hallucinate or add information not present in the context.
- Cite relevant details where useful.
"""),
    ("human", """Context:
{context}

Question: {question}

Answer:"""),
])


# HYDE prompt — output is used as a semantic search query only,
# NEVER shown to the user.
HYDE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You write short, factual hypothetical passages used \
for semantic document retrieval. Write a single dense paragraph that \
would answer the user's question if it appeared in a textbook or \
technical reference. Use domain-specific terminology. Do not refuse, \
do not hedge, do not say you don't know. Output only the paragraph."""),
    ("human", "Question: {question}\n\nPassage:"),
])


# Query-rewrite prompt — turns follow-ups into standalone questions.
REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You rewrite follow-up questions into standalone \
questions using the conversation history.

Rules:
- If the question is already standalone, return it unchanged.
- Otherwise, resolve pronouns and implicit references using the history.
- Preserve the user's intent and specificity.
- Output ONLY the rewritten question, nothing else."""),
    ("human", """Conversation history:
{history}

Follow-up question: {question}

Standalone question:"""),
])
