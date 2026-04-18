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
    from cray.api import create_app
    try:
        import uvicorn        
    except ImportError:
        console.print("[red]Error:[/red] Web dependencies not installed")
        console.print("Install with: pip install cray")
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


# Plugin marketplace commands
@main.group()
def plugin():
    """Manage plugins from the marketplace."""
    pass


@plugin.command("search")
@click.argument("query", default="")
@click.option("--keyword", "-k", multiple=True, help="Filter by keyword")
@click.option("--limit", "-l", default=20, help="Maximum results")
def plugin_search(query: str, keyword: tuple, limit: int):
    """Search for plugins in the marketplace."""
    from cray.plugins.market import PluginMarket

    market = PluginMarket()
    plugins = market.search(query, list(keyword) if keyword else None, limit)

    if not plugins:
        console.print("[yellow]No plugins found[/yellow]")
        return

    table = Table(title=f"Plugin Search Results ({len(plugins)} found)")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Description", style="white")
    table.add_column("Rating", style="yellow")
    table.add_column("Downloads", style="dim")
    table.add_column("Status", style="magenta")

    for p in plugins:
        status = "[green]installed[/green]" if p.installed else ""
        table.add_row(
            p.name,
            p.version,
            p.description[:50] + "..." if len(p.description) > 50 else p.description,
            f"⭐ {p.rating}",
            f"{p.downloads:,}",
            status
        )

    console.print(table)
    console.print(f"\n[dim]Use 'cray plugin info <name>' for details[/dim]")


@plugin.command("info")
@click.argument("name")
def plugin_info(name: str):
    """Show detailed information about a plugin."""
    from cray.plugins.market import PluginMarket

    market = PluginMarket()
    info = market.get_info(name)

    if not info:
        console.print(f"[red]Plugin '{name}' not found[/red]")
        sys.exit(1)

    status = "[green]installed[/green]" if info.installed else "[yellow]not installed[/yellow]"

    console.print(Panel(
        f"[bold cyan]{info.name}[/bold cyan] v{info.version}\n"
        f"\n{info.description}\n"
        f"\n[dim]Author:[/dim] {info.author}\n"
        f"[dim]License:[/dim] {info.license}\n"
        f"[dim]Rating:[/dim] ⭐ {info.rating} ({info.downloads:,} downloads)\n"
        f"[dim]Status:[/dim] {status}",
        title="📦 Plugin Info"
    ))

    if info.keywords:
        console.print(f"\n[bold]Keywords:[/bold] {', '.join(info.keywords)}")

    if info.actions:
        console.print("\n[bold]Actions:[/bold]")
        for action in info.actions:
            console.print(f"  • {action}")

    if info.dependencies:
        console.print(f"\n[bold]Dependencies:[/bold] {', '.join(info.dependencies)}")

    if info.installed:
        console.print(f"\n[green]✓ Installed (v{info.installed_version})[/green]")
    else:
        console.print(f"\n[dim]Install with: cray plugin install {name}[/dim]")


@plugin.command("install")
@click.argument("name")
@click.option("--version", "-v", help="Specific version to install")
@click.option("--force", "-f", is_flag=True, help="Force reinstall")
def plugin_install(name: str, version: Optional[str], force: bool):
    """Install a plugin from the marketplace."""
    from cray.plugins.market import PluginMarket

    market = PluginMarket()

    console.print(f"[cyan]Installing plugin '{name}'...[/cyan]")

    if market.install(name, version, force):
        console.print(f"[green]✓[/green] Plugin '{name}' installed successfully")
    else:
        console.print(f"[red]✗[/red] Failed to install plugin '{name}'")
        sys.exit(1)


@plugin.command("uninstall")
@click.argument("name")
def plugin_uninstall(name: str):
    """Uninstall a plugin."""
    from cray.plugins.market import PluginMarket

    market = PluginMarket()

    if market.uninstall(name):
        console.print(f"[green]✓[/green] Plugin '{name}' uninstalled")
    else:
        console.print(f"[red]✗[/red] Failed to uninstall plugin '{name}'")
        sys.exit(1)


@plugin.command("update")
@click.argument("name", required=False)
@click.option("--all", "-a", "update_all", is_flag=True, help="Update all plugins")
def plugin_update(name: Optional[str], update_all: bool):
    """Update installed plugins."""
    from cray.plugins.market import PluginMarket

    market = PluginMarket()

    if update_all:
        console.print("[cyan]Updating all installed plugins...[/cyan]")
        results = market.update_all()

        for plugin_name, success in results.items():
            status = "[green]✓[/green]" if success else "[red]✗[/red]"
            console.print(f"  {status} {plugin_name}")

    elif name:
        if market.update(name):
            console.print(f"[green]✓[/green] Plugin '{name}' updated")
        else:
            console.print(f"[red]✗[/red] Failed to update plugin '{name}'")
            sys.exit(1)
    else:
        console.print("[red]Error:[/red] Specify a plugin name or use --all")
        sys.exit(1)


@plugin.command("list")
@click.option("--installed", "-i", "only_installed", is_flag=True, help="Show only installed")
def plugin_list(only_installed: bool):
    """List plugins."""
    from cray.plugins.market import PluginMarket

    market = PluginMarket()

    if only_installed:
        installed = market.list_installed()

        if not installed:
            console.print("[yellow]No plugins installed[/yellow]")
            return

        table = Table(title="Installed Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description", style="white")

        for name, manifest in installed.items():
            desc = manifest.description[:40] + "..." if len(manifest.description) > 40 else manifest.description
            table.add_row(name, manifest.version, desc)

        console.print(table)
    else:
        # Show all available plugins
        plugins = market.search(limit=50)

        table = Table(title="Available Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description", style="white")
        table.add_column("Status", style="magenta")

        for p in plugins:
            status = "[green]installed[/green]" if p.installed else ""
            desc = p.description[:40] + "..." if len(p.description) > 40 else p.description
            table.add_row(p.name, p.version, desc, status)

        console.print(table)


if __name__ == "__main__":
    main()
