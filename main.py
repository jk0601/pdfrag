"""
main.py - PDF-RAG 프로젝트 메인 엔트리포인트
===============================================
터미널에서 실행하는 CLI(명령줄 인터페이스)를 제공합니다.

[사용법]
  # 웹 UI 실행 (권장)
  streamlit run app.py

  # 파일 업로드 (처리 → 분할 → 임베딩 → DB 저장)
  python main.py upload 파일경로.pdf

  # 여러 파일 한 번에 업로드
  python main.py upload 파일1.pdf 파일2.pptx 이미지.png

  # 챗봇 시작 (대화형)
  python main.py chat

  # 저장된 문서 목록 보기
  python main.py list

  # 문서 삭제
  python main.py delete 문서ID

  # 설정 확인
  python main.py check
"""

import sys
import os

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from config import Config
from pipeline import ingest_file, SUPPORTED_EXTENSIONS
from chatbot.chat import RAGChatbot
from database.supabase_client import SupabaseDB

console = Console()


def print_banner():
    """프로그램 시작 배너를 출력합니다."""
    banner = """
╔══════════════════════════════════════════╗
║         📚 PDF-RAG 문서 챗봇 📚         ║
║                                          ║
║  파일을 업로드하고 AI에게 질문하세요!    ║
║  PDF, 이미지, PPTX 지원                 ║
╚══════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def cmd_check():
    """설정이 올바른지 확인합니다."""
    console.print("\n[bold]🔍 설정 확인 중...[/bold]\n")

    errors = Config.validate()
    if errors:
        console.print("[red]❌ 설정 오류:[/red]")
        for err in errors:
            console.print(f"  • {err}", style="red")
        console.print(
            "\n[yellow]💡 .env 파일을 확인해 주세요. "
            ".env.example을 참고하세요.[/yellow]"
        )
        return False
    else:
        console.print("[green]✅ 모든 설정이 정상입니다![/green]")

        table = Table(title="현재 설정")
        table.add_column("항목", style="cyan")
        table.add_column("값", style="green")
        table.add_row("임베딩 모델", Config.EMBEDDING_MODEL)
        table.add_row("임베딩 차원", str(Config.EMBEDDING_DIMENSION))
        table.add_row("챗봇 모델", Config.CHAT_MODEL)
        table.add_row("청크 크기", f"{Config.CHUNK_SIZE}자")
        table.add_row("청크 겹침", f"{Config.CHUNK_OVERLAP}자")
        table.add_row("Supabase URL", Config.SUPABASE_URL[:40] + "...")
        console.print(table)
        return True


def cmd_upload(file_paths: list[str]):
    """파일을 업로드하고 처리합니다."""
    if not file_paths:
        console.print("[red]❌ 파일 경로를 지정해 주세요.[/red]")
        console.print("사용법: python main.py upload 파일경로.pdf")
        return

    errors = Config.validate()
    if errors:
        console.print("[red]❌ 먼저 설정을 완료해 주세요 (python main.py check)[/red]")
        return

    for file_path in file_paths:
        if not os.path.exists(file_path):
            console.print(f"[red]❌ 파일을 찾을 수 없습니다: {file_path}[/red]")
            continue

        console.print(f"\n[bold]📤 파일 처리 시작: {os.path.basename(file_path)}[/bold]")
        console.print(f"   경로: {os.path.abspath(file_path)}")
        console.print(f"   크기: {os.path.getsize(file_path):,} bytes\n")

        try:
            def on_progress(percent, message):
                console.print(f"  [{percent:3d}%] {message}")

            result = ingest_file(file_path, on_progress=on_progress)

            if "error" in result:
                console.print(f"[red]❌ 처리 실패: {result['error']}[/red]")
            else:
                console.print(
                    Panel(
                        f"[green]✅ 업로드 완료![/green]\n\n"
                        f"  문서 ID: {result['document_id']}\n"
                        f"  파일명: {result['filename']}\n"
                        f"  파일 종류: {result['file_type']}\n"
                        f"  청크 수: {result['chunk_count']}개",
                        title="처리 결과",
                        border_style="green",
                    )
                )
        except Exception as e:
            console.print(f"[red]❌ 오류 발생: {e}[/red]")


def cmd_list():
    """저장된 문서 목록을 표시합니다."""
    errors = Config.validate()
    if errors:
        console.print("[red]❌ 먼저 설정을 완료해 주세요[/red]")
        return

    db = SupabaseDB()
    documents = db.list_documents()

    if not documents:
        console.print("[yellow]📭 저장된 문서가 없습니다.[/yellow]")
        console.print("python main.py upload 파일경로.pdf 로 문서를 추가해 보세요.")
        return

    table = Table(title=f"📚 저장된 문서 목록 ({len(documents)}개)")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("파일명", style="green")
    table.add_column("종류", style="yellow")
    table.add_column("크기", justify="right")
    table.add_column("페이지", justify="right")
    table.add_column("등록일", style="dim")

    for doc in documents:
        size = doc.get("file_size", 0)
        if size > 1_000_000:
            size_str = f"{size / 1_000_000:.1f} MB"
        elif size > 1_000:
            size_str = f"{size / 1_000:.1f} KB"
        else:
            size_str = f"{size} B"

        table.add_row(
            str(doc["id"]),
            doc["filename"],
            doc["file_type"],
            size_str,
            str(doc.get("page_count", "-")),
            doc.get("created_at", "")[:19],
        )

    console.print(table)


def cmd_delete(doc_id: str):
    """문서를 삭제합니다."""
    errors = Config.validate()
    if errors:
        console.print("[red]❌ 먼저 설정을 완료해 주세요[/red]")
        return

    try:
        doc_id_int = int(doc_id)
    except ValueError:
        console.print("[red]❌ 문서 ID는 숫자여야 합니다.[/red]")
        return

    db = SupabaseDB()
    doc = db.get_document(doc_id_int)

    if not doc:
        console.print(f"[red]❌ 문서 ID {doc_id_int}을 찾을 수 없습니다.[/red]")
        return

    confirm = input(f"'{doc['filename']}' 문서를 삭제하시겠습니까? (y/N): ")
    if confirm.lower() == "y":
        db.delete_document(doc_id_int)
        console.print(f"[green]✅ 문서 '{doc['filename']}'이 삭제되었습니다.[/green]")
    else:
        console.print("삭제가 취소되었습니다.")


def cmd_chat():
    """대화형 챗봇을 시작합니다."""
    errors = Config.validate()
    if errors:
        console.print("[red]❌ 먼저 설정을 완료해 주세요 (python main.py check)[/red]")
        return

    console.print(
        Panel(
            "[bold cyan]💬 RAG 챗봇 시작![/bold cyan]\n\n"
            "저장된 문서를 바탕으로 질문에 답변합니다.\n"
            "종료하려면 'quit' 또는 'exit'를 입력하세요.\n"
            "대화 초기화: 'reset'",
            border_style="cyan",
        )
    )

    chatbot = RAGChatbot()

    while True:
        try:
            console.print()
            question = console.input("[bold green]❓ 질문: [/bold green]")
            question = question.strip()

            if not question:
                continue
            if question.lower() in ("quit", "exit", "종료", "q"):
                console.print("[dim]👋 챗봇을 종료합니다.[/dim]")
                break
            if question.lower() in ("reset", "초기화"):
                chatbot.reset_history()
                console.print("[yellow]🔄 대화 기록이 초기화되었습니다.[/yellow]")
                continue

            console.print("\n[bold blue]🤖 답변:[/bold blue]")
            answer = chatbot.ask(question, stream=True)

        except KeyboardInterrupt:
            console.print("\n[dim]👋 챗봇을 종료합니다.[/dim]")
            break
        except Exception as e:
            console.print(f"[red]❌ 오류: {e}[/red]")


def print_help():
    """도움말을 출력합니다."""
    help_text = """
## 사용법

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `upload` | 파일 업로드 및 처리 | `python main.py upload 보고서.pdf` |
| `chat` | 대화형 챗봇 시작 | `python main.py chat` |
| `list` | 저장된 문서 목록 | `python main.py list` |
| `delete` | 문서 삭제 | `python main.py delete 1` |
| `check` | 설정 확인 | `python main.py check` |

## 지원 파일 형식
- **PDF**: .pdf
- **이미지**: .png, .jpg, .jpeg, .gif, .bmp, .tiff, .webp
- **PowerPoint**: .pptx

## 시작하기
1. `.env.example`을 `.env`로 복사
2. `.env`에 API 키 입력
3. `python main.py check`로 설정 확인
4. `python main.py upload 파일.pdf`로 문서 업로드
5. `python main.py chat`로 질문하기
    """
    console.print(Markdown(help_text))


def main():
    """메인 함수: 명령줄 인수를 파싱하여 적절한 명령을 실행합니다."""
    print_banner()

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "upload":
        cmd_upload(sys.argv[2:])
    elif command == "chat":
        cmd_chat()
    elif command == "list":
        cmd_list()
    elif command == "delete":
        if len(sys.argv) < 3:
            console.print("[red]❌ 삭제할 문서 ID를 지정하세요.[/red]")
            console.print("사용법: python main.py delete 문서ID")
        else:
            cmd_delete(sys.argv[2])
    elif command == "check":
        cmd_check()
    elif command in ("help", "-h", "--help"):
        print_help()
    else:
        console.print(f"[red]❌ 알 수 없는 명령: {command}[/red]")
        print_help()


if __name__ == "__main__":
    main()
