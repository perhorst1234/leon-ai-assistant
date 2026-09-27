"""Bounded coding subprocess using the persistent M40 thermal guard."""
import argparse
import os
import signal
import subprocess
import time

from leon_control_plane import thermal_guard
from leon_control_plane.openai_text import ModelPreflightError


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # A exited parent can leave children alive; terminate the entire own group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


def sample(limit):
    thermal_guard.check()
    value = thermal_guard.load().get('temperature_c')
    if type(value) is not int or value >= limit:
        raise ModelPreflightError('local_gpu_too_hot')
    return value


def run(command, *, seconds=600, limit=89, probe=sample, clock=time.monotonic, sleep=time.sleep):
    if type(seconds) is not int or not 10 <= seconds <= 3600 or type(limit) is not int or not 65 <= limit <= 89:
        raise ValueError('Invalid coding process limits')
    peak = probe(limit)
    process = subprocess.Popen(command, start_new_session=True)
    started = clock()
    try:
        while process.poll() is None:
            try:
                peak = max(peak, probe(limit))
            except ModelPreflightError:
                return 75
            if clock()-started >= seconds:
                return 124
            sleep(0.5)
        return process.returncode
    finally:
        stop(process)
        print(f'M40 coding peak sampled temperature: {peak}C',flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds',type=int,default=600)
    parser.add_argument('--limit',type=int,default=89)
    parser.add_argument('--model',required=True)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:
        parser.error('Coding command required')
    def interrupted(signum,frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,interrupted)
    code = 130
    try:
        code = run(command,seconds=args.seconds,limit=args.limit)
    finally:
        if code != 0:
            try:
                subprocess.run(['ollama','stop',args.model],capture_output=True,timeout=3,check=False)
            except (OSError,subprocess.TimeoutExpired):
                pass
    raise SystemExit(code)


if __name__ == '__main__':
    main()
