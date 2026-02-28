"""
chat.py - RAG 기반 챗봇
=========================
사용자의 질문에 대해 저장된 문서를 참고하여 답변하는 챗봇입니다.

[초보자 안내]
RAG 챗봇의 작동 방식:
1. 사용자가 질문을 입력합니다
2. 질문과 관련된 문서 조각을 DB에서 검색합니다 (Retriever)
3. 검색된 조각들을 AI 모델에게 "참고자료"로 전달합니다
4. AI 모델이 참고자료를 바탕으로 답변을 생성합니다

일반 ChatGPT와의 차이:
- ChatGPT: 학습 데이터만으로 답변 → 우리 문서 내용은 모름
- RAG 챗봇: 우리 문서를 검색해서 참고 → 정확한 답변 가능

프롬프트 엔지니어링:
- AI에게 "역할"과 "규칙"을 정해주는 것
- 예: "주어진 참고자료만 사용해서 답변하세요"
"""

from openai import OpenAI

from config import Config
from rag.retriever import Retriever


SYSTEM_PROMPT = """당신은 문서 기반 질의응답 AI 어시스턴트입니다.

## 규칙
1. 반드시 아래 제공된 참고자료만을 바탕으로 답변하세요.
2. 참고자료에 없는 내용은 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답하세요.
3. 답변할 때 어떤 참고자료를 근거로 했는지 출처를 명시하세요.
4. 한국어로 답변하세요.
5. 답변은 명확하고 구조적으로 작성하세요.

## 참고자료
{context}
"""


class RAGChatbot:
    """
    RAG 기반 챗봇 클래스

    사용 예시:
        chatbot = RAGChatbot()
        answer = chatbot.ask("2024년 매출이 얼마인가요?")
        print(answer)
    """

    def __init__(self, top_k: int = 5, threshold: float = 0.2):
        """
        Args:
            top_k: 검색할 최대 문서 조각 수
            threshold: 최소 유사도 임계값
        """
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.retriever = Retriever()
        self.model = Config.CHAT_MODEL
        self.top_k = top_k
        self.threshold = threshold
        self.conversation_history: list[dict] = []

    def ask(self, question: str, stream: bool = False) -> str:
        """
        질문에 대해 답변합니다.

        Args:
            question: 사용자 질문
            stream: True면 스트리밍 응답 (터미널에서 실시간 출력)

        Returns:
            AI의 답변 텍스트
        """
        context = self.retriever.search_with_context(
            query=question,
            top_k=self.top_k,
            threshold=self.threshold,
        )

        system_message = SYSTEM_PROMPT.format(context=context)

        messages = [
            {"role": "system", "content": system_message},
            *self.conversation_history,
            {"role": "user", "content": question},
        ]

        if stream:
            return self._stream_response(messages, question)
        else:
            return self._get_response(messages, question)

    def _get_response(self, messages: list[dict], question: str) -> str:
        """일반 응답 (전체 답변을 한 번에 반환)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        answer = response.choices[0].message.content or ""

        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": answer})

        # 대화 기록이 너무 길어지면 오래된 것부터 제거
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-10:]

        return answer

    def _stream_response(self, messages: list[dict], question: str) -> str:
        """스트리밍 응답 (터미널용, 글자가 하나씩 나타남)"""
        full_response = ""
        for chunk_text in self._stream_chunks(messages):
            print(chunk_text, end="", flush=True)
            full_response += chunk_text
        print()

        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append(
            {"role": "assistant", "content": full_response}
        )
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-10:]

        return full_response

    def stream_answer(self, question: str):
        """
        Streamlit 등 웹 UI용 스트리밍 제너레이터.
        yield로 한 조각씩 텍스트를 반환합니다.

        사용 예시 (Streamlit):
            for chunk in chatbot.stream_answer("매출은?"):
                st.write(chunk)
        """
        context = self.retriever.search_with_context(
            query=question,
            top_k=self.top_k,
            threshold=self.threshold,
        )
        system_message = SYSTEM_PROMPT.format(context=context)
        messages = [
            {"role": "system", "content": system_message},
            *self.conversation_history,
            {"role": "user", "content": question},
        ]

        full_response = ""
        for chunk_text in self._stream_chunks(messages):
            full_response += chunk_text
            yield chunk_text

        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append(
            {"role": "assistant", "content": full_response}
        )
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-10:]

    def _stream_chunks(self, messages: list[dict]):
        """OpenAI 스트리밍 응답에서 텍스트 조각을 yield합니다."""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def reset_history(self):
        """대화 기록을 초기화합니다."""
        self.conversation_history.clear()
