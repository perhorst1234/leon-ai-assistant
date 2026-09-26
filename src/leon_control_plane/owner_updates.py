"""Durable, deduplicated Leon messages for meaningful background events."""
from contextlib import closing
import time
import uuid

from leon_control_plane.secret_scanner import assert_no_secrets


def publish(store, event_key, content):
    from leon_control_plane.chat_api import ChatService
    if not isinstance(content, str) or not 1 <= len(content.encode()) <= 12000:
        raise ValueError('Invalid owner update')
    assert_no_secrets('Owner update', content)
    service = ChatService(store)
    conversation = service.create_conversation({
        'request_id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'leon:owner-updates')),
        'title': 'Leon updates',
    })
    with closing(store.connect()) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS owner_updates(event_key TEXT PRIMARY KEY, message_id TEXT NOT NULL)')
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM owner_updates WHERE event_key=?', (event_key,)).fetchone():
            return False
        mid = 'update-' + uuid.uuid5(uuid.NAMESPACE_URL, event_key).hex
        now = max(time.time(), conn.execute('SELECT COALESCE(MAX(created_at),0)+0.000001 FROM chat_messages WHERE conversation_id=?', (conversation['id'],)).fetchone()[0])
        conn.execute("INSERT INTO chat_messages(id,conversation_id,role,content,status,created_at,updated_at,execution_kind) VALUES(?,?,'assistant',?,'complete',?,?,'action')", (mid, conversation['id'], content, now, now))
        conn.execute('UPDATE chat_conversations SET revision=revision+1,updated_at=? WHERE id=?', (now, conversation['id']))
        conn.execute('INSERT INTO owner_updates VALUES(?,?)', (event_key, mid))
    return True
