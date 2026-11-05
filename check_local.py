"""离线检查，不读取密钥、不请求真实模型。--student 检查两项学生任务。"""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch, MagicMock
import csv, json, math, sys
import rag_core as core
from model_client import ModelError


def main():
    pieces=core.chunk_text('甲乙丙丁戊己庚辛壬癸',6,2)
    assert [(a,b) for a,b,_ in pieces]==[(0,6),(4,10)]
    assert pieces[0][2][-2:]==pieces[1][2][:2]
    assert abs(core.cosine([1,0],[1,0])-1)<1e-9
    assert abs(core.cosine([1,0],[0,1]))<1e-9
    large=core.cosine([1e308,1e308],[1e308,1e308])
    assert math.isfinite(large) and abs(large-1)<1e-9, '大数值向量计算不正确。'
    for a,b in [([0,0],[1,1]),([1,0],[1])]:
        try: core.cosine(a,b)
        except ModelError: pass
        else: raise AssertionError('非法向量应被拦截')
    chunks,sources=core.load_chunks(Path(__file__).resolve().parent/'data',180,30)
    assert len(sources)>=3 and len({c['chunk_id'] for c in chunks})==len(chunks)
    assert all(c['source'] and c['end']-c['start']==len(c['text']) for c in chunks)
    with (Path(__file__).resolve().parent/'questions.csv').open(encoding='utf-8-sig',newline='') as file:
        questions=list(csv.DictReader(file))
    assert [q['编号'] for q in questions]==[f'T{i:02d}' for i in range(1,11)], '题目编号应为T01至T10。'
    assert sum(q['类型']=='库外' for q in questions)==2, '应有2道资料外问题。'
    assert all(all(q.values()) for q in questions), '题目表有缺失字段。'
    cfg={'embedding_endpoint':'https://example.invalid/embeddings','embedding_model':'offline-model'}
    fake=MagicMock()
    fake.__enter__.return_value.read.return_value=json.dumps({'data':[
        {'index':1,'embedding':[0,1]},{'index':0,'embedding':[1,0]}]}).encode()
    with patch('rag_core.request.build_opener') as opener:
        opener.return_value.open.return_value=fake
        assert core.embed_texts(cfg,'FAKE_TEST_KEY',['甲','乙'])==[[1,0],[0,1]]
        req=opener.return_value.open.call_args.args[0]
        assert json.loads(req.data)['input']==['甲','乙']
    print('基础检查通过：中文资料、题目表、分块、相似度与模拟接口响应。')
    if '--student' not in sys.argv:
        print('完成rag_core.py的两项任务后，增加 --student 参数检查；当前不是完整功能验收。')
        return
    demo=[{'chunk_id':'A','source':'a.md','text':'甲','embedding':[1,0]},
          {'chunk_id':'B','source':'b.md','text':'乙','embedding':[0,1]}]
    before=deepcopy(demo)
    hits=core.select_top_k(demo,[0,1],1)
    assert hits[0]['chunk_id']=='B','学生任务一尚未完成：应按相似度降序取前k条。'
    assert before==demo,'不能改写原始索引。'
    history=[{'role':'user','content':'上一轮问题'},{'role':'assistant','content':'上一轮回答'}]
    snapshot=deepcopy(history)
    messages=core.build_rag_messages('规则',history,'当前问题',hits)
    assert messages[0]=={'role':'system','content':'规则'} and messages[1:3]==history
    user=messages[-1]
    assert user['role']=='user' and '当前问题' in user['content']
    assert '[B]' in user['content'] and 'b.md' in user['content'] and '乙' in user['content'], '学生任务二尚未完成：本轮user消息须含编号、来源、正文与问题。'
    assert history==snapshot
    empty=core.build_rag_messages('规则',[],'新问题',[])
    assert len(empty)==2 and empty[-1]['role']=='user'
    print('两项学生任务结构检查通过；实际检索和问答质量仍须通过真实接口检查。')


if __name__=='__main__':
    if not __debug__:
        print('请不要使用-O或-OO运行本检查，否则检查语句会被跳过。')
        raise SystemExit(1)
    try:
        main()
    except (AssertionError, ModelError, OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print('检查未通过：',str(exc) or '请检查两处代码任务及文件内容。')
        raise SystemExit(1)
