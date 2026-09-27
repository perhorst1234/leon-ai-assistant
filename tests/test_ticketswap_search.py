import uuid
import pytest
from leon_control_plane.ticketswap_search import search,execute,SOURCE,LIMIT
from leon_control_plane.chat_actions import route,apply,may_be_action
from test_control_plane import make_store

HTML='<a href="https://www.ticketswap.nl/concert-tickets/example-artist-2027-id"><h3>Example Artist</h3><span>Amsterdam 2027</span></a>'


def test_public_sources_only_no_price_or_availability_invention():
    bad='<a href="https://evil.example/concert-tickets/x">Wrong</a><a href="https://www.ticketswap.nl/checkout">Buy</a>'
    d=search('Example',reader=lambda:bad+HTML+HTML)
    assert len(d['events'])==1 and d['cost_microusd']==0 and d['prices_verified'] is False
    assert d['source']==SOURCE and 'Example Artist' in d['events'][0]['description']
    assert search('Unknown',reader=lambda:HTML)['events']==[]
    for html in ('<h1>Access denied</h1>','x'*(LIMIT+1)):
        with pytest.raises(ValueError):search(reader=lambda:html)


def test_example_routes_without_gpu_and_result_tracks_in_work(tmp_path):
    store=make_store(tmp_path);request_id=str(uuid.uuid4())
    content='Zoek op TicketSwap een voorbeeldconcert in Nederland.'
    assert may_be_action(content)
    assert route(content,[],{})=={'action':'tickets.search','args':{'query':''}}
    assert route('Maak een Python tool voor TicketSwap, met een voorbeeld.',[],{})=={'action':'code.build','args':{}}
    result=execute(store,request_id,reader=lambda:HTML)
    assert 'niets gekocht' in result
    assert execute(store,request_id,reader=lambda:pytest.fail('duplicate read'))==result
    with store.connect() as c:
        task=c.execute("SELECT status,owner FROM tasks WHERE title LIKE 'TicketSwap:%'").fetchone()
    assert task['status']=='done' and task['owner']=='Leon Shopper'
    with pytest.raises(ValueError):apply(store,str(uuid.uuid4()),{'action':'tickets.search','args':{'query':''}},None,owner_content='Zoek Marktplaats RAM.')


def test_blocked_provider_stays_visible_as_blocked(tmp_path):
    store=make_store(tmp_path)
    result=execute(store,str(uuid.uuid4()),reader=lambda:(_ for _ in ()).throw(ValueError('private error')))
    assert 'niet bevestigd' in result
    with store.connect() as c:
        assert c.execute("SELECT status FROM tasks WHERE title LIKE 'TicketSwap:%'").fetchone()[0]=='blocked'
        assert 'private error' not in '\n'.join(c.iterdump())
