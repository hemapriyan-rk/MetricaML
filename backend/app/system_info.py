"""Describes the machine the experiments run on (EC2 instance metadata when available)."""
import os
import platform
import urllib.request
from functools import lru_cache

import numpy
import pandas
import sklearn

_IMDS = "http://169.254.169.254/latest"


def _imds(path: str, token: str) -> str:
    req = urllib.request.Request(f"{_IMDS}/meta-data/{path}", headers={"X-aws-ec2-metadata-token": token})
    return urllib.request.urlopen(req, timeout=0.5).read().decode()


def _ec2_metadata() -> dict | None:
    """Query the EC2 instance metadata service (IMDSv2). Returns None off AWS."""
    try:
        req = urllib.request.Request(f"{_IMDS}/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"})
        token = urllib.request.urlopen(req, timeout=0.5).read().decode()
        return {
            "instance_type": _imds("instance-type", token),
            "instance_id": _imds("instance-id", token),
            "zone": _imds("placement/availability-zone", token),
        }
    except Exception:
        return None


def _os_name() -> str:
    try:
        with open("/etc/os-release") as fh:
            for line in fh:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return f"{platform.system()} {platform.release()}"


def _memory_mb() -> int | None:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


@lru_cache(maxsize=1)
def get_host() -> dict:
    ec2 = _ec2_metadata()
    return {
        "provider": "AWS EC2" if ec2 else "Local machine",
        "instance_type": ec2["instance_type"] if ec2 else None,
        "instance_id": ec2["instance_id"] if ec2 else None,
        "zone": ec2["zone"] if ec2 else None,
        "os": _os_name(),
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "pandas": pandas.__version__,
        "numpy": numpy.__version__,
        "cpu_count": os.cpu_count(),
        "memory_mb": _memory_mb(),
    }
