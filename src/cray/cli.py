"""
Cray CLI - Command Line Interface.
"""

import sys
from pathlib import Path
from typing import Optional
import asyncio

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from loguru import logger

from cray import __version__
from cray.core.workflow import Workflow
from cray.core.runner import Runner
from cray.plugins import PluginManager


console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )


@click.group()
@click.version_option(version=__version__, prog_name="cray")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def main(verbose: bool):
    """
    Cray - A lightweight automation tool with claws 🦞
    
    Run workflows with simple YAML configurations.
    """
    setup_logging(verbose)


@main.command()
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--input", "-i", "input_data", help="JSON input data for workflow")
@click.option("--dry-run", is_flag=True, help="Validate workflow without executing")
def run(workflow_file: str, input_data: Optional[str], dry_run: bool):
    """Run a workflow from YAML file."""
    
    workflow_path = Path(workflow_file)
    
    console.print(Panel(
        f"[bold blue]Cray[/bold blue] v{__version__}\n"
        f"Workflow: [green]{workflow_path.name}[/green]",
        title="🦞 Cray Runner"
    ))
    
    try:
        # Load workflow
        workflow = Workflow.from_yaml(workflow_path)
        
        # Validate
        errors = workflow.validate_steps()
        if errors:
            for error in errors:
                console.print(f"[red]Error:[/red] {error}")
            sys.exit(1)
        
        if dry_run:
            console.print("[yellow]Dry run mode - workflow validated successfully[/yellow]")
            console.print(f"\n[bold]Workflow:[/bold] {workflow.name}")
            console.print(f"[bold]Steps:[/bold] {len(workflow.steps)}")
            for i, step in enumerate(workflow.steps, 1):
                console.print(f"  {i}. {step.name} ({step.plugin}.{step.action})")
            return
        
        # Parse input data
        parsed_input = {}
        if input_data:
            import json
            parsed_input = json.loads(input_data)
        
        # Run workflow
        runner = Runner()
        task = asyncio.run(runner.run(workflow, parsed_input))
        
        # Display results
        if task.status.value == "success":
            console.print(f"\n[green]✓[/green] Workflow completed successfully")
            console.print(f"  Duration: {task.duration_seconds:.2f}s")
            
            if task.output:
                console.print("\n[bold]Output:[/bold]")
                for key, value in task.output.items():
                    console.print(f"  {key}: {value}")
        else:
            console.print(f"\n[red]✗[/red] Workflow failed: {task.error}")
            sys.exit(1)
            
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Workflow execution failed")
        sys.exit(1)


@main.command("list")
@click.option("--plugins", is_flag=True, help="List available plugins")
def list_items(plugins: bool):
    """List workflows or plugins."""
    
    if plugins:
        # List plugins
        table = Table(title="Available Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        
        manager = PluginManager()
        for name, desc in manager.list_plugins().items():
            table.add_row(name, desc)
        
        console.print(table)
    else:
        # List workflow files in current directory
        workflows = list(Path(".").glob("*.yaml")) + list(Path(".").glob("*.yml"))
        
        if not workflows:
            console.print("[yellow]No workflow files found in current directory[/yellow]")
            return
        
        table = Table(title="Workflow Files")
        table.add_column("File", style="cyan")
        table.add_column("Size", style="white")
        
        for wf in workflows:
            size = wf.stat().st_size
            table.add_row(str(wf), f"{size} bytes")
        
        console.print(table)


@main.command()
@click.argument("name", default="my-workflow")
def create(name: str):
    """Create a new workflow template."""
    
    workflow = Workflow(
        name=name,
        description="A new Cray workflow",
        steps=[
            {
                "name": "hello",
                "plugin": "shell",
                "action": "exec",
                "params": {"command": "echo 'Hello from Cray!'"}
            }
        ]
    )
    
    filename = f"{name}.yaml"
    workflow.to_yaml(filename)
    
    console.print(f"[green]✓[/green] Created workflow: {filename}")
    console.print(f"\nEdit the file and run with: [cyan]cray run {filename}[/cyan]")


@main.command()
@click.argument("workflow_file", type=click.Path(exists=True))
def validate(workflow_file: str):
    """Validate a workflow file."""
    
    workflow_path = Path(workflow_file)
    
    try:
        workflow = Workflow.from_yaml(workflow_path)
        errors = workflow.validate_steps()
        
        if errors:
            console.print("[red]Validation failed:[/red]")
            for error in errors:
                console.print(f"  - {error}")
            sys.exit(1)
        
        console.print("[green]✓[/green] Workflow is valid")
        console.print(f"\n[bold]Name:[/bold] {workflow.name}")
        console.print(f"[bold]Version:[/bold] {workflow.version}")
        console.print(f"[bold]Steps:[/bold] {len(workflow.steps)}")
        
        table = Table(title="Workflow Steps")
        table.add_column("#", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Plugin", style="green")
        table.add_column("Action", style="yellow")
        
        for i, step in enumerate(workflow.steps, 1):
            table.add_row(str(i), step.name, step.plugin, step.action)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.group()
def schedule():
    """Manage scheduled workflows."""
    pass


@schedule.command("add")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--cron", help="Cron expression (e.g., '0 9 * * *')")
@click.option("--interval", type=int, help="Interval in seconds")
def schedule_add(workflow_file: str, cron: Optional[str], interval: Optional[int]):
    """Schedule a workflow."""
    from cray.scheduler import Scheduler
    
    if not cron and not interval:
        console.print("[red]Error:[/red] Must specify --cron or --interval")
        sys.exit(1)
    
    workflow_path = Path(workflow_file)
    workflow = Workflow.from_yaml(workflow_path)
    
    scheduler = Scheduler()
    scheduler.start()
    
    job_id = scheduler.schedule_workflow(
        workflow,
        cron=cron,
        interval_seconds=interval,
    )
    
    console.print(f"[green]✓[/green] Scheduled workflow '{workflow.name}'")
    console.print(f"  Job ID: {job_id}")
    
    if cron:
        console.print(f"  Cron: {cron}")
    else:
        console.print(f"  Interval: {interval}s")


@schedule.command("list")
def schedule_list():
    """List scheduled workflows."""
    from cray.scheduler import Scheduler
    
    scheduler = Scheduler()
    jobs = scheduler.list_jobs()
    
    if not jobs:
        console.print("[yellow]No scheduled workflows[/yellow]")
        return
    
    table = Table(title="Scheduled Workflows")
    table.add_column("Job ID", style="cyan")
    table.add_column("Workflow", style="green")
    table.add_column("Schedule", style="yellow")
    table.add_column("Next Run", style="dim")
    
    for job_id, info in jobs.items():
        schedule = info.get("cron") or f"every {info.get('interval_seconds')}s"
        table.add_row(
            job_id,
            info["workflow"],
            schedule,
            info.get("next_run", "-")
        )
    
    console.print(table)


@schedule.command("remove")
@click.argument("job_id")
def schedule_remove(job_id: str):
    """Remove a scheduled workflow."""
    from cray.scheduler import Scheduler
    
    scheduler = Scheduler()
    
    if scheduler.unschedule(job_id):
        console.print(f"[green]✓[/green] Removed job: {job_id}")
    else:
        console.print(f"[red]Error:[/red] Job not found: {job_id}")
        sys.exit(1)


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", default=8000, help="Port to bind")
@click.option("--workflow-dir", default="./workflows", help="Workflow directory")
def serve(host: str, port: int, workflow_dir: str):
    """Start the web API server."""
    try:
        import uvicorn
        from cray.api import create_app
    except ImportError:
        console.print("[red]Error:[/red] Web dependencies not installed")
        console.print("Install with: pip install cray[web]")
        sys.exit(1)

    console.print(Panel(
        f"[bold blue]Cray Web API[/bold blue]\n"
        f"Host: [green]{host}[/green]\n"
        f"Port: [green]{port}[/green]\n"
        f"Workflows: [green]{workflow_dir}[/green]",
        title="🦞 Starting Server"
    ))

    app = create_app(workflows_dir=workflow_dir)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
