from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from .models import TracerouteHop, TracerouteResult


@dataclass
class TracerouteHopRaw:
    hop: int
    ip: Optional[str]
    hostname: Optional[str]
    latencies: list[float]
    loss: float


def run_traceroute_windows(ip: str, max_hops: int = 30, timeout_seconds: float = 5.0) -> list[TracerouteHopRaw]:
    """Executa tracert no Windows e retorna lista de hops brutos."""
    timeout_ms = int(timeout_seconds * 1000)
    cmd = ["tracert", "-h", str(max_hops), "-w", str(timeout_ms), "-d", ip]
    
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_hops * timeout_seconds + 30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return []
    
    return _parse_tracert_output(completed.stdout)


def run_traceroute_unix(ip: str, max_hops: int = 30, timeout_seconds: float = 5.0) -> list[TracerouteHopRaw]:
    """Executa traceroute no Unix/Linux e retorna lista de hops brutos."""
    cmd = ["traceroute", "-m", str(max_hops), "-w", str(int(timeout_seconds)), "-n", ip]
    
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_hops * timeout_seconds + 30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return []
    
    return _parse_traceroute_output(completed.stdout)


def _parse_tracert_output(output: str) -> list[TracerouteHopRaw]:
    """Parseia saída do tracert Windows."""
    hops = []
    # Formato típico:
    #  1     1 ms     1 ms     1 ms  192.168.1.1
    #  1     <1 ms    <1 ms    <1 ms  192.168.1.1
    #  2     *        *        *     Request timed out.
    #  3    10 ms    11 ms    10 ms  10.0.0.1
    
    lines = output.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("Tracing route") or line.startswith("Trace complete"):
            continue
        
        # Match: hop_number  latencies  ip_or_timeout
        match = re.match(
            r"^\s*(\d+)\s+(.+?)\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-f0-9:.:]+)\s*$",
            line,
            re.IGNORECASE
        )
        if not match:
            # Tenta match com timeout
            match = re.match(r"^\s*(\d+)\s+(.+?)\s*$", line)
            if match:
                hop_num = int(match.group(1))
                latency_str = match.group(2).strip()
                latencies = []
                loss = 100.0
                for part in latency_str.split():
                    part = part.replace("ms", "").strip()
                    if part == "*" or part == "Request" or part == "timed" or part == "out.":
                        continue
                    try:
                        latencies.append(float(part))
                    except ValueError:
                        pass
                if latencies:
                    loss = 0.0
                hops.append(TracerouteHopRaw(
                    hop=hop_num,
                    ip=None,
                    hostname=None,
                    latencies=latencies,
                    loss=loss
                ))
            continue
        
        hop_num = int(match.group(1))
        latency_str = match.group(2).strip()
        ip = match.group(3).strip()
        
        latencies = []
        for part in latency_str.split():
            part = part.replace("ms", "").replace("<", "").strip()
            if part == "*":
                continue
            try:
                latencies.append(float(part))
            except ValueError:
                pass
        
        loss = 100.0 if not latencies else 0.0
        
        hops.append(TracerouteHopRaw(
            hop=hop_num,
            ip=ip if ip != "*" else None,
            hostname=None,
            latencies=latencies,
            loss=loss
        ))
    
    return hops


def _parse_traceroute_output(output: str) -> list[TracerouteHopRaw]:
    """Parseia saída do traceroute Unix/Linux."""
    hops = []
    # Formato típico:
    # 1  192.168.1.1  1.234 ms  1.123 ms  1.456 ms
    # 2  * * *
    # 3  10.0.0.1  10.2 ms  10.5 ms  10.1 ms
    
    lines = output.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("traceroute to"):
            continue
        
        # Match: hop  ip/hostname  latencies
        parts = line.split()
        if not parts:
            continue
        
        try:
            hop_num = int(parts[0])
        except ValueError:
            continue
        
        if len(parts) < 2:
            continue
        
        # Segundo campo pode ser IP ou hostname
        ip = None
        hostname = None
        idx = 1
        
        # Verifica se segundo campo é IP
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", parts[1]) or ":" in parts[1]:
            ip = parts[1]
            idx = 2
        else:
            hostname = parts[1]
            idx = 2
            # Próximo pode ser IP
            if idx < len(parts) and (re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", parts[idx]) or ":" in parts[idx]):
                ip = parts[idx]
                idx += 1
        
        latencies = []
        loss = 100.0
        for i in range(idx, len(parts)):
            part = parts[i].replace("ms", "").strip()
            if part == "*":
                continue
            try:
                latencies.append(float(part))
            except ValueError:
                pass
        
        if latencies:
            loss = 0.0
        
        hops.append(TracerouteHopRaw(
            hop=hop_num,
            ip=ip,
            hostname=hostname,
            latencies=latencies,
            loss=loss
        ))
    
    return hops


def run_traceroute(
    ip: str,
    max_hops: int = 30,
    timeout_seconds: float = 5.0,
) -> TracerouteResult:
    """Executa traceroute e retorna resultado estruturado."""
    if sys.platform == "win32":
        raw_hops = run_traceroute_windows(ip, max_hops, timeout_seconds)
    else:
        raw_hops = run_traceroute_unix(ip, max_hops, timeout_seconds)
    
    if not raw_hops:
        return TracerouteResult(
            target_ip=ip,
            max_hops=max_hops,
            total_hops=0,
            destination_reached=False,
            hops=[],
        )
    
    # Converte para hops estruturados
    hops = []
    destination_reached = False
    
    for raw in raw_hops:
        avg_latency = sum(raw.latencies) / len(raw.latencies) if raw.latencies else None
        
        hop = TracerouteHop(
            hop_number=raw.hop,
            ip=raw.ip,
            hostname=raw.hostname,
            latency_ms=avg_latency,
            packet_loss_percent=raw.loss,
        )
        hops.append(hop)
        
        # Verifica se chegou ao destino (último hop com IP igual ao target)
        if raw.ip and raw.ip == ip:
            destination_reached = True
    
    return TracerouteResult(
        target_ip=ip,
        max_hops=max_hops,
        total_hops=len(hops),
        destination_reached=destination_reached,
        hops=hops,
    )