from contextlib import closing
import json
import uuid

import pytest

from leon_control_plane.chat_api import ChatService, _memory_context
from leon_control_plane.conversation_learning import reflect, validate
from test_control_plane import make_store


def message(store, text, now=100.):
    conversation = ChatService(store).create_conversation({'request_id': str(uuid.uuid4())})
    mid = 'chatmsg-' + uuid.uuid4().hex
    with closing(store.connect()) as conn, conn:
        conn.execute("INSERT INTO chat_messages(id,conversation_id,role,content,status,created_at,updated_at) VALUES(?,?,'user',?,'complete',?,?)", (mid, conversation['id'], text, now, now))
    return mid


def reflection(mid, kind, quote, text='Gebruik korte informele antwoorden.'):
    return {'items': [{'message_id': mid, 'kind': kind, 'quote': quote, 'text': text}]}


def test_local_learning_is_grounded_used_in_chat_and_not_repeated(tmp_path):
    store = make_store(tmp_path)
    quote = 'Ik wil korte informele antwoorden.'
    mid = message(store, quote)
    def model(group):
        assert group == [{'id': mid, 'content': quote}]
        return reflection(mid, 'preference', quote)
    assert reflect(store, model=model, clock=lambda: 101)['preferences'] == 1
    with closing(store.connect()) as conn:
        assert quote in _memory_context(conn, 'Hallo')
    assert reflect(store, model=lambda _: pytest.fail('repeated inference'), clock=lambda: 102) == {'preferences': 0, 'tools': 0, 'questions': 0}


def test_tool_becomes_real_work_prompt_and_question_is_delivered(tmp_path):
    store = make_store(tmp_path)
    tool = 'Ik wil een koppeling met mijn printer.'
    mid = message(store, tool)
    def model(group):
        return {'items': [reflection(mid, 'tool', tool, 'Maak een Fluidd-koppeling voor printerstatus.')['items'][0],
                          reflection(mid, 'question', tool, 'Welke Fluidd-server gebruikt je printer?')['items'][0]]}
    result = reflect(store, model=model, clock=lambda: 101)
    assert result['tools'] == result['questions'] == 1
    with closing(store.connect()) as conn:
        tasks = conn.execute("SELECT goal,approval_required FROM tasks WHERE owner='Leon Zelfleren'").fetchall()
        assert len(tasks) == 2 and all(not r['approval_required'] for r in tasks)
        assert any('Bouwprompt:' in r['goal'] and 'Nog niet uitgevoerd' in r['goal'] for r in tasks)
        assert conn.execute("SELECT 1 FROM chat_messages WHERE role='assistant' AND content LIKE '%Welke Fluidd-server%' AND status='complete'").fetchone()


@pytest.mark.parametrize('kind,quote', [('preference','Ik wil verzonnen informatie.'), ('tool','Installeer nu een tool.'), ('question','Een onbestaand citaat.')])
def test_hallucinated_sources_and_implicit_requests_are_rejected(kind, quote):
    with pytest.raises(ValueError):
        validate(reflection('one',kind,quote), [{'id':'one','content':'Hoi, ik heb vandaag een printer gebruikt.'}])


def test_credentials_never_reach_model_and_do_not_block_future_messages(tmp_path):
    store = make_store(tmp_path)
    message(store,'Mijn wachtwoord is geheim.'); mid = message(store,'Ik wil korte antwoorden.')
    groups = []
    assert reflect(store, model=lambda g: groups.append(g) or reflection(mid,'preference',g[0]['content']), clock=lambda:101,notify=False)['preferences']==1
    assert len(groups)==1 and len(groups[0])==1
    assert reflect(store,model=lambda _:pytest.fail('credential loop'),clock=lambda:102,notify=False)['preferences']==0


def test_related_old_preference_is_not_silently_overwritten(tmp_path):
    store=make_store(tmp_path)
    old=store.create_memory_item({'content':'Ik wil lange formele antwoorden over printer instellingen.', 'source':'owner', 'status':'active','memory_type':'preference'})
    quote='Ik wil korte informele antwoorden over printer instellingen.'; mid=message(store,quote)
    reflect(store,model=lambda _:reflection(mid,'preference',quote),clock=lambda:101,notify=False)
    with closing(store.connect()) as conn:
        new=conn.execute('SELECT status,conflict_status,conflict_memory_ids_json FROM memory_items WHERE content=?',(quote,)).fetchone()
        assert new['status']=='candidate' and new['conflict_status']=='conflicted'
        assert old in json.loads(new['conflict_memory_ids_json'])
        assert conn.execute('SELECT status FROM memory_items WHERE id=?',(old,)).fetchone()[0]=='active'


def test_interrupted_notification_resumes_without_duplicate_effect_or_inference(tmp_path, monkeypatch):
    store=make_store(tmp_path); quote='Ik wil korte antwoorden.'; mid=message(store,quote)
    from leon_control_plane import owner_updates
    original=owner_updates.publish
    monkeypatch.setattr(owner_updates,'publish',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError):
        reflect(store,model=lambda _:reflection(mid,'preference',quote),clock=lambda:101)
    monkeypatch.setattr(owner_updates,'publish',original)
    reflect(store,model=lambda _:pytest.fail('repeated inference'),clock=lambda:102)
    with closing(store.connect()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM memory_items WHERE content=?',(quote,)).fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM owner_updates').fetchone()[0]==1


def test_invalid_output_does_not_consume_message(tmp_path):
    store=make_store(tmp_path);mid=message(store,'Ik wil korte antwoorden.')
    with pytest.raises(ValueError):
        reflect(store,model=lambda _:reflection(mid,'preference','Ik wil andere woorden.'),clock=lambda:101,notify=False)
    assert reflect(store,model=lambda g:reflection(mid,'preference',g[0]['content']),clock=lambda:102,notify=False)['preferences']==1


def test_preference_quote_can_be_a_grounded_following_sentence():
    text='Ik wil eigenlijk alles gratis. Als het geld kost, moet ik even over nadenken.'
    quote='Als het geld kost, moet ik even over nadenken.'
    assert validate(reflection('one','preference',quote),[{'id':'one','content':text}])[0]['quote']==quote
