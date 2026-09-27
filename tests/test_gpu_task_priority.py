from contextlib import closing
import uuid

from leon_control_plane.chat_api import ChatService
from leon_control_plane.local_model import LocalModelConfig
from leon_control_plane.work_queue import WorkQueue,MODEL_KIND
from leon_control_plane.model_work import ModelExecutor
from test_control_plane import make_store


def test_chat_queue_priority_uses_stored_chat_identity_and_older_work_eventually_wins(tmp_path):
    store=make_store(tmp_path);chat=ChatService(store);now=[100.]
    queue=WorkQueue(store,clock=lambda:now[0],local_model_config=LocalModelConfig(enabled=True))
    task=store.create_task(title='Research',goal='Research',risk_level='low')
    def enqueue(t):
        return queue.enqueue(task_id=t,request_id=str(uuid.uuid4()),kind=MODEL_KIND,
            model_request={'prompt':'Hallo','max_output_tokens':32,'max_cost_microusd':1,'provider':'ollama','approve_external_text':True})
    bg=enqueue(task);now[0]=101
    conversation=chat.create_conversation({'request_id':str(uuid.uuid4())})
    with closing(store.connect()) as c:
        chat_task=c.execute('SELECT task_id FROM chat_conversations WHERE id=?',(conversation['id'],)).fetchone()[0]
    foreground=enqueue(chat_task)
    with closing(store.connect()) as c,c:
        c.execute("INSERT INTO chat_messages(id,conversation_id,role,content,status,created_at,updated_at,job_id) VALUES(?,?,'assistant','test','pending',?,?,?)",
            ('test-message',conversation['id'],now[0],now[0],foreground['id']))
    claimed=queue.claim();assert claimed['id']==foreground['id']
    priorities=[]
    def local(payload,config):
        priorities.append(config.gpu_priority)
        return {'model':payload['model'],'done':True,'done_reason':'stop','response':'OK','prompt_eval_count':2,'eval_count':1}
    executor=ModelExecutor(queue,local_config=LocalModelConfig(enabled=True),local_transport=local)
    assert executor.execute(claimed)['ok'] and priorities==['chat']
    queue.control(foreground['id'],'pause');queue.control(foreground['id'],'resume')
    now[0]=162
    claimed=queue.claim();assert claimed['id']==bg['id']
    assert executor.execute(claimed)['ok'] and priorities==['chat','background']
