"""Docker boundary shared by OpenSkill role tools and executor-owned measurements.

The host is trusted. No role receives the Docker socket, host credentials, journal,
SDK state or another role's workspace. An unavailable boundary is an error.
"""

import json
import fcntl
import os
import signal
import stat
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from artifacts import require


def stamp():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def regular(root, relative):
    """Reject links (including hard links), devices and traversal before crossing roles."""
    rel = Path(relative)
    require(not rel.is_absolute() and rel.parts and ".." not in rel.parts, "Expected a relative file path")
    cursor = root
    require(not root.is_symlink(), "Linked staging root")
    for part in rel.parts:
        cursor = cursor / part
        require(not cursor.is_symlink(), f"Linked artifact: {relative}")
    info = cursor.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, f"Not an unlinked regular file: {relative}")
    require(cursor.resolve().is_relative_to(root.resolve()), "Artifact escapes its root")
    return cursor


def copy_files(source, destination, names):
    require(len(names) == len(set(names)), "Duplicate artifact paths")
    for name in names:
        origin = regular(source, name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        require(not target.exists() and not target.is_symlink(), "Never overwrite staged evidence")
        target.write_bytes(origin.read_bytes())
        target.chmod(0o644 | (origin.stat().st_mode & 0o111))


def files(root):
    require(root.is_dir() and not root.is_symlink(), "Missing or linked artifact directory")
    found = []
    for entry in sorted(root.rglob("*")):
        require(not entry.is_symlink(), "Linked artifact directory or file")
        if not entry.is_dir():
            name = entry.relative_to(root).as_posix()
            regular(root, name)
            found.append(name)
    require(found, "Empty artifact directory")
    return found


class Interrupted(RuntimeError):
    pass


class CleanupFailed(RuntimeError):
    pass


class Boundary:
    def __init__(self, config, control, work, readonly, deadline, stop):
        self.config = config
        self.control = control
        self.work = work.resolve()
        self.readonly = [p.resolve() for p in readonly]
        self.deadline = datetime.fromisoformat(deadline).timestamp()
        self.stop = stop
        self.name = "openskill-" + uuid.uuid4().hex
        self.docker = config["docker"]
        self.record = control / (self.name + ".json")
        self.uid = config["uid"]
        self.gid = config["gid"]
        require(type(self.uid) is int and self.uid > 0 and type(self.gid) is int and self.gid > 0,
                "Role tools must run as a non-root uid and gid")
        for path in [self.work, *self.readonly]:
            require(path.is_dir() and "," not in str(path), "Invalid container mount")
        for left in [self.work, *self.readonly]:
            for right in [self.work, *self.readonly]:
                require(left == right or not left.is_relative_to(right), "Overlapping role mounts")

    def check(self):
        if self.stop.exists():
            raise Interrupted("Experiment STOP fence is set")
        if time.time() >= self.deadline:
            raise Interrupted("Construction deadline reached")

    def docker_call(self, args):
        return subprocess.run([self.docker, *args], text=True, capture_output=True, timeout=30, check=True)

    def __enter__(self):
        self.check()
        image = self.config["image"]
        require(image.startswith("sha256:") and len(image) == 71, "Pin the local sanitized image by its sha256 id")
        inspected = json.loads(self.docker_call(["image", "inspect", image]).stdout)[0]
        require(inspected["Id"] == image, "Image identity changed")
        # Record before creation: stop/recovery can remove a container after a host crash.
        save(self.record, {"container": self.name, "status": "starting", "image": image,
                           "work": str(self.work), "readonly": list(map(str, self.readonly)), "started_at": stamp()})
        args = ["run", "--detach", "--name", self.name, "--label", "openskill.control=" + str(self.control),
                "--network", "none", "--ipc", "private", "--cap-drop", "ALL",
                "--cap-add", "CHOWN", "--cap-add", "SETUID", "--cap-add", "SETGID",
                "--security-opt", "no-new-privileges", "--pids-limit", "256",
                "--memory", self.config.get("memory", "4g"), "--cpus", str(self.config.get("cpus", 2)),
                "--mount", f"type=bind,src={self.work},dst={self.work}"]
        for path in self.readonly:
            args += ["--mount", f"type=bind,src={path},dst={path},readonly"]
        node = Path(self.config["node"]).resolve()
        require(node.is_file() and "," not in str(node), "Missing Node executable")
        args += ["--mount", f"type=bind,src={node},dst=/opt/openskill-node,readonly"]
        if self.config.get("entrypoint"):
            args += ["--entrypoint", self.config["entrypoint"]]
        args += [image, *self.config.get("command", [])]
        try:
            self.docker_call(args)
            # This also verifies the image can run the SDK's confined file worker.
            probe = self.docker_call(self.exec_argv([
                "/opt/openskill-node", "-e",
                "if(process.getuid()===0)process.exit(1);process.stdout.write('ready')"])[1:])
            require(probe.stdout == "ready", "Non-root file worker preflight failed")
            self.check()
            return self
        except BaseException:
            self.close()
            raise

    def exec_argv(self, argv, cwd=None):
        return [self.docker, "exec", "-i", "--user", f"{self.uid}:{self.gid}",
                "--workdir", str(cwd or self.work), self.name, "/usr/bin/env", "-i",
                "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp", "LANG=C.UTF-8",
                "PYTHONDONTWRITEBYTECODE=1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1", *argv]

    def run(self, argv, log, cwd=None):
        """Capture a real process result; cancellation kills all container descendants."""
        self.check()
        started = stamp()
        status, code = "interrupted", None
        log.parent.mkdir(parents=True, exist_ok=True)
        process = None
        try:
            with log.open("wb") as output:
                output.write((json.dumps({"argv": argv, "started_at": started}) + "\n").encode())
                output.flush()
                process = subprocess.Popen(self.exec_argv(argv, cwd), stdout=output, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                while process.poll() is None:
                    self.check()
                    try:
                        process.wait(timeout=0.2)
                    except subprocess.TimeoutExpired:
                        pass
                self.check()
                code, status = process.returncode, "completed"
        finally:
            if process and process.poll() is None:
                self.close()
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # docker exec can exit while container removal completes.
                process.wait()
            save(log.with_suffix(".process.json"), {"argv": argv, "started_at": started,
                 "finished_at": stamp(), "execution_status": status, "exit_code": code})
        return json.loads(log.with_suffix(".process.json").read_text())

    def close(self):
        # Only our random, labelled container can be removed; no daemon-wide cleanup.
        try:
            stop_container(self.docker, self.control, self.name)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.stop.write_text("Container cleanup is unconfirmed; do not continue.\n")
            raise CleanupFailed(f"Could not confirm shutdown of {self.name}") from exc
        if self.record.exists():
            record = json.loads(self.record.read_text())
            record.update(status="stopped", stopped_at=stamp())
            save(self.record, record)

    def __exit__(self, *_):
        self.close()


def stop_container(docker, control, name):
    require(name.startswith("openskill-") and len(name) == 42, "Invalid owned container name")
    control.mkdir(parents=True, exist_ok=True)
    with (control / (name + ".stop.lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _stop_container(docker, control, name)


def _stop_container(docker, control, name):
    result = subprocess.run([docker, "inspect", name], text=True, capture_output=True, timeout=30)
    if result.returncode:
        # A missing container is fine; an unavailable daemon is not a confirmed stop.
        subprocess.run([docker, "info", "--format", "{{.ID}}"], capture_output=True, timeout=30, check=True)
        return
    info = json.loads(result.stdout)[0]
    require(info["Config"].get("Labels", {}).get("openskill.control") == str(control),
            "Refusing to stop an unowned container")
    removed = subprocess.run([docker, "rm", "--force", "--volumes", name], capture_output=True, timeout=30)
    if removed.returncode:
        # STOP and a worker's finally can remove the same container concurrently.
        absent = subprocess.run([docker, "inspect", name], capture_output=True, timeout=30)
        if absent.returncode:
            subprocess.run([docker, "info", "--format", "{{.ID}}"], capture_output=True, timeout=30, check=True)
            return
        removed.check_returncode()
