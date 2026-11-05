"""RAG核心：字符分块、嵌入调用、余弦相似度与消息构造。"""
from pathlib import Path
from urllib import request, error
from http.client import HTTPException
import hashlib
import json
import math
import tempfile
from model_client import ModelError, validate_endpoint


def chunk_text(text, size, overlap):
    if (isinstance(size, bool) or isinstance(overlap, bool)
            or not isinstance(size, int) or not isinstance(overlap, int)
            or not 0 <= overlap < size):
        raise ModelError("分块参数须为整数，且 0 <= chunk_overlap < chunk_size。")
    result = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        result.append((start, end, text[start:end]))
        if end == len(text):
            break
        start = end - overlap
    return result


def load_chunks(data_dir, size, overlap):
    # 即使资料文件夹为空，也先检查分块参数。
    chunk_text("", size, overlap)
    chunks, sources = [], []
    try:
        files = sorted(path for path in Path(data_dir).iterdir()
                       if path.is_file() and path.suffix.lower() in (".txt", ".md"))
    except OSError:
        raise ModelError("无法读取data文件夹，请确认文件夹存在且可以访问。") from None
    for doc_no, path in enumerate(files, 1):
        try:
            # 同时接受普通UTF-8和Windows编辑器保存的带BOM的UTF-8。
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            raise ModelError(f"资料“{path.name}”的编码不正确，请用编辑器另存为UTF-8。") from None
        except OSError:
            raise ModelError(f"无法读取资料“{path.name}”，请检查文件和权限。") from None
        if not text.strip():
            raise ModelError(f"资料“{path.name}”没有正文，请补充内容或将空文件移出data。")
        sources.append({"source": path.name,
                        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
        for number, (start, end, content) in enumerate(chunk_text(text, size, overlap), 1):
            chunks.append({"chunk_id": f"D{doc_no:02d}-C{number:03d}", "source": path.name,
                           "start": start, "end": end, "text": content})
    if not chunks:
        raise ModelError("data中没有可读取的UTF-8文本资料。")
    return chunks, sources


def manifest_for(cfg, sources):
    return {"embedding_model": cfg["embedding_model"], "embedding_endpoint": cfg["embedding_endpoint"],
            "chunk_size": cfg["chunk_size"], "chunk_overlap": cfg["chunk_overlap"], "sources": sources}


def validate_embedding_config(cfg):
    if not isinstance(cfg, dict):
        raise ModelError("嵌入配置必须是对象，请检查config.json。")
    validate_endpoint(cfg.get("embedding_endpoint", ""), "嵌入接口地址")
    if not isinstance(cfg.get("embedding_model"), str) or not cfg["embedding_model"].strip():
        raise ModelError("请教师配置embedding_model。")


def validate_vector(vector):
    if not isinstance(vector, list) or not vector:
        raise ModelError("嵌入向量为空或格式不符。")
    try:
        valid = all(not isinstance(value, bool) and isinstance(value, (int, float))
                    and math.isfinite(value) for value in vector)
    except (OverflowError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ModelError("嵌入向量包含无效数值。")
    if not any(value != 0 for value in vector):
        raise ModelError("嵌入向量不能全部为零。")


def _validate_vectors(vectors, expected_count):
    if not isinstance(vectors, list) or len(vectors) != expected_count or not vectors:
        raise ModelError("嵌入向量数量与资料片段数量不符，请重新建库。")
    for vector in vectors:
        validate_vector(vector)
    if len({len(vector) for vector in vectors}) != 1:
        raise ModelError("文档向量维度不一致，请确认嵌入模型后重新建库。")


def embed_texts(cfg, key, texts):
    validate_embedding_config(cfg)
    if not isinstance(key, str) or not key.strip():
        raise ModelError("嵌入接口密钥不能为空。")
    if (not isinstance(texts, list) or not texts
            or any(not isinstance(text, str) or not text for text in texts)):
        raise ModelError("待嵌入内容须为非空文本列表。")
    timeout = cfg.get("timeout_seconds", 45)
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not 1 <= timeout <= 120):
        raise ModelError("timeout_seconds应为1至120的数值。")

    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        payload = json.dumps({"model": cfg["embedding_model"], "input": texts},
                             ensure_ascii=False).encode("utf-8")
        req = request.Request(cfg["embedding_endpoint"], data=payload, method="POST", headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with request.build_opener(NoRedirect()).open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8-sig"))
    except error.HTTPError as exc:
        raise ModelError(f"嵌入接口HTTP {exc.code}，请核对权限、模型及批量上限。") from None
    except (error.URLError, HTTPException, TimeoutError, OSError, TypeError, ValueError, UnicodeError):
        raise ModelError("嵌入请求失败或返回不是有效JSON。") from None

    rows = data.get("data") if isinstance(data, dict) else None
    if (not isinstance(rows, list) or len(rows) != len(texts)
            or any(not isinstance(row, dict) for row in rows)):
        raise ModelError("嵌入响应的数量或结构不符，请教师检查接入层。")
    indices = [row.get("index") for row in rows]
    if (any(type(index) is not int for index in indices)
            or sorted(indices) != list(range(len(texts)))):
        raise ModelError("嵌入响应的索引不正确，请教师检查接入层。")
    vectors = [row.get("embedding") for row in sorted(rows, key=lambda row: row["index"])]
    _validate_vectors(vectors, len(texts))
    return vectors


def cosine(a, b):
    validate_vector(a)
    validate_vector(b)
    if len(a) != len(b):
        raise ModelError("查询与文档向量维度不同，须使用同一嵌入模型并重新建库。")
    # 先缩放再归一化，避免平方大数溢出或平方小数变为零。
    scale_a, scale_b = max(abs(value) for value in a), max(abs(value) for value in b)
    scaled_a = [value / scale_a for value in a]
    scaled_b = [value / scale_b for value in b]
    norm_a = math.sqrt(math.fsum(value * value for value in scaled_a))
    norm_b = math.sqrt(math.fsum(value * value for value in scaled_b))
    score = math.fsum((x / norm_a) * (y / norm_b) for x, y in zip(scaled_a, scaled_b))
    if not math.isfinite(score):
        raise ModelError("无法计算有效相似度，请检查嵌入向量。")
    return max(-1.0, min(1.0, score))


def select_top_k(chunks, query_vector, k):
    scored = [dict(c, score=cosine(query_vector, c["embedding"])) for c in chunks]
    # 学生任务一：按score从大到小排序，再取前k个。
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:k]


def format_context(hits):
    return "\n\n".join(f'[{h["chunk_id"]}] 来源：{h["source"]}\n{h["text"]}' for h in hits)


def build_rag_messages(system_prompt, history, question, hits):
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(dict(item) for item in history)
    # 学生任务二：用format_context(hits)组织参考资料，与当前问题一起写入本轮user消息。
    context = format_context(hits)
    content = ("参考资料：\n" + context + "\n\n当前问题：" + question) if context else question
    messages.append({"role": "user", "content": content})
    return messages


def _chunk_settings(cfg):
    try:
        size, overlap = cfg["chunk_size"], cfg["chunk_overlap"]
    except KeyError:
        raise ModelError("缺少chunk_size或chunk_overlap，请检查配置。") from None
    chunk_text("", size, overlap)
    return size, overlap


def build_index(cfg, key, data_dir, index_file):
    validate_embedding_config(cfg)
    size, overlap = _chunk_settings(cfg)
    chunks, sources = load_chunks(data_dir, size, overlap)
    batch = cfg.get("embedding_batch_size", 8)
    if not isinstance(batch, int) or isinstance(batch, bool) or batch < 1:
        raise ModelError("embedding_batch_size须为正整数。")
    vectors = []
    for start in range(0, len(chunks), batch):
        vectors.extend(embed_texts(cfg, key, [c["text"] for c in chunks[start:start + batch]]))
    # 全部批次一起检查，通过后再保存，避免写入混合维度的知识库。
    _validate_vectors(vectors, len(chunks))
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    index = {"manifest": manifest_for(cfg, sources), "chunks": chunks}
    destination = Path(index_file)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="\n",
                                         dir=destination.parent, prefix=destination.name + ".",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(index, stream, ensure_ascii=False, indent=2, allow_nan=False)
        temporary.replace(destination)
    except (OSError, TypeError, ValueError):
        raise ModelError("知识库保存失败，请检查目录和写入权限；原文件未被替换。") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return index


def read_index(cfg, data_dir, index_file):
    validate_embedding_config(cfg)
    size, overlap = _chunk_settings(cfg)
    expected_chunks, sources = load_chunks(data_dir, size, overlap)
    try:
        index = json.loads(Path(index_file).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        raise ModelError("没有有效知识库，请执行/index。") from None
    if not isinstance(index, dict) or not isinstance(index.get("manifest"), dict):
        raise ModelError("知识库格式不正确，请执行/index重新建库。")
    if index["manifest"] != manifest_for(cfg, sources):
        raise ModelError("资料、分块或嵌入模型已改变，请执行/index重新建库。")
    chunks = index.get("chunks")
    if not isinstance(chunks, list) or not chunks or len(chunks) != len(expected_chunks):
        raise ModelError("知识库片段数量不正确，请执行/index重新建库。")
    for chunk, expected in zip(chunks, expected_chunks):
        if (not isinstance(chunk, dict) or set(chunk) != set(expected) | {"embedding"}
                or type(chunk.get("start")) is not int or type(chunk.get("end")) is not int
                or any(chunk.get(field) != value for field, value in expected.items())):
            raise ModelError("知识库片段与原资料不一致，请执行/index重新建库。")
    _validate_vectors([chunk["embedding"] for chunk in chunks], len(chunks))
    return index
