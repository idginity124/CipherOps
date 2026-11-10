import asyncio
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .core.agent import AgentEvent, CipherAgent
from .core.llm import create_llm_client
from .guardrails.command_validator import RiskLevel
from .guardrails.pii_sanitizer import PIISanitizer
from .memory import MemoryStore
from .tools.registry import create_default_registry

app = typer.Typer(
    name="cipherops",
    help="CipherOps: local-first tool-calling agent with user-managed memory.",
    add_completion=False,
)
console = Console()
memory_app = typer.Typer(help="Manage user-approved local memories.", no_args_is_help=True)
app.add_typer(memory_app, name="memory")


def _make_llm_client(provider: str, base_url: str | None, model: str | None):
    try:
        return create_llm_client(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=os.getenv("CIPHEROPS_LOCAL_API_KEY"),
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _get_enabled_memory(enabled: bool) -> MemoryStore | None:
    if not enabled:
        return None
    store = MemoryStore()
    memories = store.list_memories()
    if not memories:
        console.print("[yellow]No saved memories yet. Add one with `cipherops memory add`. [/]")
        return None
    preview, _ = PIISanitizer().sanitize(store.context_text())
    console.print(
        Panel(Text(preview), title="Saved notes to be included", border_style="yellow")
    )
    if not Confirm.ask(
        "Send these notes to the configured model server for this session?", default=False
    ):
        return None
    return store


@memory_app.command("list")
def memory_list():
    """List locally saved memories."""
    store = MemoryStore()
    memories = store.list_memories()
    if not memories:
        console.print(f"No memories saved in {store.path}")
        return
    table = Table(title=f"Saved memories · {store.path}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Content")
    table.add_column("Updated", style="dim")
    for memory in memories:
        table.add_row(
            str(memory.id),
            Text(memory.title),
            Text(memory.content),
            memory.updated_at,
        )
    console.print(table)


@memory_app.command("add")
def memory_add(
    title: str = typer.Argument(..., help="Short name for this memory"),
    content: str = typer.Argument(..., help="The exact information to remember"),
):
    """Save a memory explicitly; CipherOps never creates memories automatically."""
    try:
        memory = MemoryStore().add(title, content)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Saved memory #{memory.id}: {memory.title}")


@memory_app.command("edit")
def memory_edit(
    memory_id: int = typer.Argument(..., help="Memory ID from `cipherops memory list`"),
    title: str | None = typer.Option(None, help="New title"),
    content: str | None = typer.Option(None, help="Replacement content"),
):
    """Edit a saved memory by ID."""
    if title is None and content is None:
        raise typer.BadParameter("Provide --title or --content.")
    try:
        memory = MemoryStore().update(memory_id, title=title, content=content)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if memory is None:
        raise typer.BadParameter(f"Memory #{memory_id} does not exist.")
    console.print(f"Updated memory #{memory.id}: {memory.title}")


@memory_app.command("delete")
def memory_delete(
    memory_id: int = typer.Argument(..., help="Memory ID from `cipherops memory list`"),
):
    """Delete one saved memory after confirmation."""
    store = MemoryStore()
    memory = store.get(memory_id)
    if memory is None:
        raise typer.BadParameter(f"Memory #{memory_id} does not exist.")
    if Confirm.ask(f"Delete memory #{memory.id} ({memory.title})?", default=False):
        store.delete(memory_id)
        console.print("Memory deleted.")
    else:
        console.print("Cancelled.")


@memory_app.command("clear")
def memory_clear():
    """Delete all saved memories after confirmation."""
    store = MemoryStore()
    count = len(store.list_memories())
    if count == 0:
        console.print("No memories to delete.")
        return
    if Confirm.ask(f"Delete all {count} saved memories?", default=False):
        store.clear()
        console.print(f"Deleted {count} memories.")
    else:
        console.print("Cancelled.")


def human_approval_callback(command: str, risk_level: RiskLevel, reason: str) -> bool:
    """Terminal Human-in-the-Loop approval prompt."""
    color = "yellow" if risk_level == RiskLevel.CAUTION else "bold red"
    console.print(
        Panel(
            f"[bold {color}]SECURITY RISK ASSESSMENT: {risk_level.value}[/]\n"
            f"[dim]Reason: {reason}[/]\n\n"
            f"[bold cyan]Command:[/] [white]{command}[/]",
            title="🛡️ Operator Confirmation Required",
            border_style=color,
        )
    )
    return Confirm.ask("Execute this command on host?", default=False)


def handle_agent_event(event: AgentEvent) -> None:
    """Render agent runtime events with rich visual elements."""
    if event.event_type == "thinking":
        console.print(
            f"[dim cyan]🧠 Step {event.data['iteration']}: Analyzing state & planning...[/]"
        )

    elif event.event_type == "pii_alert":
        console.print(
            f"[bold magenta]🔒 Privacy Guardrail:[/] Redacted {event.data['count']} sensitive tokens "
            f"({', '.join(set(event.data['types']))}) before model inference."
        )

    elif event.event_type == "message":
        console.print(Panel(event.data, title="🤖 CipherOps", border_style="cyan"))

    elif event.event_type == "tool_call":
        name = event.data["name"]
        args = event.data["arguments"]
        console.print(f"[bold yellow]⚙️ Executing Tool:[/] [green]{name}[/] args={args}")

    elif event.event_type == "tool_result":
        status = "[bold green]SUCCESS[/]" if event.data["success"] else "[bold red]FAILED[/]"
        out = event.data["output"]
        if len(out) > 600:
            out = out[:600] + "\n... [truncated for display]"
        console.print(f"   ↳ {status} (Code {event.data['exit_code']}):\n[dim]{out}[/]")

    elif event.event_type == "error":
        console.print(f"[bold red]❌ Error:[/] {event.data}")


@app.command()
def doctor(
    provider: str = typer.Option("ollama", help="Local provider: ollama or openai-compatible"),
    base_url: str | None = typer.Option(None, help="Local server URL; defaults by provider"),
):
    """Check Python, a selected local model server, and the audit directory."""
    console.print(Panel.fit("[bold cyan]CipherOps System Doctor[/]", border_style="cyan"))

    table = Table(title="System & LLM Readiness", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    # 1. Python
    table.add_row("Python Runtime", "[green]OK[/]", sys.version.split()[0])

    # 2. Selected local model server
    client = _make_llm_client(provider, base_url, None)
    is_healthy = asyncio.run(client.check_health())
    server_url = getattr(client, "base_url", "")

    if is_healthy:
        table.add_row("Local Model Server", "[green]ACTIVE[/]", f"{provider}: {server_url}")
        models = asyncio.run(client.list_local_models())
        models_str = ", ".join(models) if models else "No models downloaded yet"
        table.add_row(
            "Available Models",
            "[green]FOUND[/]" if models else "[yellow]NONE[/]",
            models_str,
        )
    else:
        table.add_row(
            "Local Model Server",
            "[red]INACTIVE[/]",
            f"Cannot connect to {provider} at {server_url}.",
        )

    # 3. Audit Directory
    audit_path = Path.home() / ".cipherops" / "audit"
    table.add_row("Audit Trail Directory", "[green]CONFIGURED[/]", str(audit_path))

    console.print(table)


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Instruction or task for CipherOps to perform"),
    model: str | None = typer.Option(None, help="Model name/tag on the selected local server"),
    provider: str = typer.Option("ollama", help="Local provider: ollama or openai-compatible"),
    base_url: str | None = typer.Option(None, help="Local server URL; defaults by provider"),
    use_memory: bool = typer.Option(False, help="Offer saved memories to the model for this task"),
):
    """Run a single task using a local model server."""
    client = _make_llm_client(provider, base_url, model)
    memory_store = _get_enabled_memory(use_memory)
    registry = create_default_registry(approval_callback=human_approval_callback)
    agent = CipherAgent(
        llm_client=client,
        memory_store=memory_store,
        registry=registry,
        event_callback=handle_agent_event,
    )

    console.print(f"[bold green]Starting CipherOps task:[/] {prompt}\n")
    asyncio.run(agent.run(prompt))
    console.print("\n[bold green]🏁 Task Complete.[/]")


@app.command()
def chat(
    model: str | None = typer.Option(None, help="Model name/tag on the selected local server"),
    provider: str = typer.Option("ollama", help="Local provider: ollama or openai-compatible"),
    base_url: str | None = typer.Option(None, help="Local server URL; defaults by provider"),
    use_memory: bool = typer.Option(False, help="Offer saved memories to the model in this session"),
):
    """Start an interactive autonomous session."""
    client = _make_llm_client(provider, base_url, model)
    memory_store = _get_enabled_memory(use_memory)
    registry = create_default_registry(approval_callback=human_approval_callback)
    agent = CipherAgent(
        llm_client=client,
        memory_store=memory_store,
        registry=registry,
        event_callback=handle_agent_event,
    )

    console.print(
        Panel(
            "[bold cyan]CipherOps Interactive Session[/]\n"
            f"[dim]Provider: {provider} | Model: {client.model or 'server default'} | "
            "Guardrails: Active | Audit: Enabled[/]\n"
            "Type 'exit' or 'quit' to terminate session. "
            "Type 'clear' to reset conversation history.",
            border_style="cyan",
        )
    )

    async def _chat_loop() -> None:
        turn = 0
        while True:
            try:
                user_input = Prompt.ask("\n[bold green]You[/]")
                stripped = user_input.strip()

                if not stripped:
                    continue

                if stripped.lower() in ("exit", "quit", "q"):
                    console.print("[dim]Session ended. Goodbye! 👋[/]")
                    break

                if stripped.lower() == "clear":
                    agent.reset()
                    console.print("[dim cyan]✓ Conversation history cleared.[/]")
                    turn = 0
                    continue

                turn += 1
                console.print(f"[dim]─── Turn {turn} ───[/]")
                await agent.run(stripped)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Session interrupted. Goodbye! 👋[/]")
                break

    asyncio.run(_chat_loop())


def main():
    app()


if __name__ == "__main__":
    main()
