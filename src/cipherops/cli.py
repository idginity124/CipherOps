import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .core.agent import AgentEvent, CipherAgent
from .core.llm import OllamaClient
from .guardrails.command_validator import RiskLevel
from .tools.registry import create_default_registry

app = typer.Typer(
    name="cipherops",
    help="CipherOps: Enterprise-Grade Local Autonomous Agent with Privacy Guardrails.",
    add_completion=False,
)
console = Console()


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
    ollama_url: str = typer.Option("http://localhost:11434", help="Ollama API base URL"),
):
    """Diagnose local system environment, GPU readiness, and Ollama status."""
    console.print(Panel.fit("[bold cyan]CipherOps System Doctor[/]", border_style="cyan"))

    table = Table(title="System & LLM Readiness", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    # 1. Python
    table.add_row("Python Runtime", "[green]OK[/]", sys.version.split()[0])

    # 2. Ollama Daemon
    client = OllamaClient(base_url=ollama_url)
    is_healthy = asyncio.run(client.check_health())

    if is_healthy:
        table.add_row("Ollama Service", "[green]ACTIVE[/]", f"Connected to {ollama_url}")
        models = asyncio.run(client.list_local_models())
        models_str = ", ".join(models) if models else "No models downloaded yet"
        table.add_row(
            "Local Models",
            "[green]FOUND[/]" if models else "[yellow]NONE[/]",
            models_str,
        )
    else:
        table.add_row(
            "Ollama Service",
            "[red]INACTIVE[/]",
            f"Cannot connect to {ollama_url}. Is 'systemctl start ollama' running?",
        )

    # 3. Audit Directory
    audit_path = Path.home() / ".cipherops" / "audit"
    table.add_row("Audit Trail Directory", "[green]CONFIGURED[/]", str(audit_path))

    console.print(table)


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Instruction or task for CipherOps to perform"),
    model: str = typer.Option("qwen2.5-coder:14b", help="Model name on local Ollama"),
    ollama_url: str = typer.Option("http://localhost:11434", help="Ollama base URL"),
):
    """Run a single autonomous task through CipherOps."""
    client = OllamaClient(base_url=ollama_url, model=model)
    registry = create_default_registry(approval_callback=human_approval_callback)
    agent = CipherAgent(
        llm_client=client,
        registry=registry,
        event_callback=handle_agent_event,
    )

    console.print(f"[bold green]Starting CipherOps task:[/] {prompt}\n")
    asyncio.run(agent.run(prompt))
    console.print("\n[bold green]🏁 Task Complete.[/]")


@app.command()
def chat(
    model: str = typer.Option("qwen2.5-coder:14b", help="Model name on local Ollama"),
    ollama_url: str = typer.Option("http://localhost:11434", help="Ollama base URL"),
):
    """Start an interactive autonomous session."""
    client = OllamaClient(base_url=ollama_url, model=model)
    registry = create_default_registry(approval_callback=human_approval_callback)
    agent = CipherAgent(
        llm_client=client,
        registry=registry,
        event_callback=handle_agent_event,
    )

    console.print(
        Panel(
            "[bold cyan]CipherOps Interactive Session[/]\n"
            f"[dim]Model: {model} | Guardrails: Active | Audit: Enabled[/]\n"
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
