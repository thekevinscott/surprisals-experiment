"""Durable, credential-free pod costs, mirrored to each owning experiment."""

import json
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value) + '\n')
    temporary.replace(path)


def registry(pod_id):
    return Path.home() / '.runpod/costs' / f'{pod_id}.json'


def record(pod, experiment, gpu):
    experiment = Path(experiment).resolve()
    path = experiment / 'runpod-costs' / f'{pod["id"]}.json'
    index = registry(pod['id'])
    if index.exists():
        entry = json.loads(index.read_text())
    else:
        entry = {'pod': {
            'id': pod['id'],
            'gpu': (pod.get('gpu') or {}).get('displayName') or gpu,
            'costPerHr': float(pod['costPerHr']),
            'start': pod.get('lastStartedAt') or now(),
            'stop': None,
        }, 'paths': []}
    if str(path) not in entry['paths']:
        entry['paths'].append(str(path))
    write(index, entry)
    write(path, entry['pod'])


def stopped(pod_id):
    index = registry(pod_id)
    if not index.exists():
        return  # Pods created before cost recording have no history.
    entry = json.loads(index.read_text())
    entry['pod']['stop'] = entry['pod']['stop'] or now()
    for path in entry['paths']:
        write(Path(path), entry['pod'])
    write(index, entry)
