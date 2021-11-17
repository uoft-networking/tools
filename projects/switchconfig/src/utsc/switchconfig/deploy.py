
import time

from . import config

from utsc.core import shell
import pexpect
from rich.progress import Progress, SpinnerColumn, TaskID



def login(p: pexpect.spawn, ssh_pass: str, status: Progress, task_id: TaskID):
    while True:
        match = p.expect(["password:", pexpect.TIMEOUT], timeout=1)
        if match == 0:
            p.sendline(ssh_pass)
            break
        else:
            status.advance(task_id)
            continue


def deploy_to_console(target: str):
    host, _, port = target.partition(":")

    ssh_pass = shell(config.data.ssh_pass_cmd)
    terminal_pass = shell(config.data.terminal_pass_cmd)
    enable_pass = shell(config.data.enable_pass_cmd)

    username = "admin"
    status = Progress(SpinnerColumn("dots5"), "{task.description}", transient=True)
    status.start()
    task_id = status.add_task(f"Connecting to {host}:{port}...")
    p = pexpect.spawn(f"ssh -l {username} -p {port} {host}")

    login(p, ssh_pass, status, task_id)

    status.console.print(f"Connected to {host}:{port}")

    status.update(task_id, description="Waiting for switch terminal to be available...")
    status.advance(task_id)

    terminal_available = False

    def terminal_now_available():
        nonlocal terminal_available
        if not terminal_available:
            terminal_available = True
            status.console.print("Switch terminal is now available and responding.")
            status.update(task_id, description="Resolving current switch state...")

    while True:
        match = p.expect(
            [
                "Press RETURN to get started.",
                "Would you like to enter the initial configuration dialog?",
                "Switch>",
                "Username:",
                "Password:",
                r"([a-zA-Z0-9-]+)>",
                r"([a-zA-Z0-9-]+)\(config\)#",
                r"([a-zA-Z0-9-]+)#",
                r"([a-zA-Z0-9-]+)\(([a-z-]+)\)#",
                pexpect.TIMEOUT,
            ],
            timeout=1,
        )

        status.advance(task_id)
        if match == 0:
            # "Press RETURN to get started."
            terminal_now_available()
            p.sendline()
            time.sleep(0.5)
            continue
        elif match == 1:
            # "Would you like to enter the initial configuration dialog?"
            terminal_now_available()
            status.console.print(
                "This switch is uninitialized, and has booted into the config wizard. Cancelling the wizard..."
            )
            p.sendline("no")
            time.sleep(0.5)
            continue
        elif match == 2:
            # "Switch>"
            terminal_now_available()
            status.console.print(
                "This switch is uninitialized. Entering enable mode now..."
            )
            p.sendline("enable")
            time.sleep(0.5)
            continue
        elif match == 3:
            # "Username:"
            terminal_now_available()
            status.console.print(
                "This switch has been at least partially initialized. Logging in now..."
            )
            p.sendline(username)
            time.sleep(0.5)
            continue
        elif match == 4:
            # "Password:"
            terminal_now_available()
            status.console.print("Entering switch password...")
            status.update(
                task_id, description="Waiting for switch authentication to complete..."
            )
            p.sendline(terminal_pass)
            time.sleep(0.5)
            continue
        elif match == 5:
            # r"([a-zA-Z0-9-]+)>"
            terminal_now_available()
            status.console.print(
                "We are now logged into a partially initialized switch. Entering 'enable' mode..."
            )
            p.sendline("enable")
            time.sleep(0.5)
            res = p.expect(["Password:", pexpect.TIMEOUT], timeout=3)
            # here we wait for 3 seconds to get a password prompt.
            # If no password prompt, assume this swtich isn't configured with an enable password
            # This may be an incorrect assumption, we may need to come back and revisit this
            if res == 0:
                p.sendline(enable_pass)
                time.sleep(1)
            continue
        elif match == 6:
            # r"([a-zA-Z0-9-]+)\(config)#"
            terminal_now_available()
            status.console.print(
                "Entered 'configure terminal' mode. Ready to process configuration"
            )
            time.sleep(0.5)
            break
        elif match == 7:
            # r"([a-zA-Z0-9-]+)#"
            terminal_now_available()
            status.console.print(
                "We have successfully entered 'enable' mode. Entering 'configure terminal' mode..."
            )
            p.sendline("configure terminal")
            time.sleep(0.5)
            continue
        elif match == 8:
            # r"([a-zA-Z0-9-]+)\(([a-z-]+)\)#"
            terminal_now_available()
            status.console.print(
                "This switch is in one of the configure modes. Dropping back down to enable mode..."
            )
            p.sendcontrol("c")
            time.sleep(0.5)
            continue
        else:
            # TIMEOUT
            # Terminal probably not ready yet.
            # let's poke it and wait a bit more
            p.sendline("\r")
            time.sleep(0.5)
            continue

    status.stop()

    p.interact()

    print()
