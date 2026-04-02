"""
vector_store.py — Chroma 向量数据库的初始化和操作封装
"""

import chromadb
from chromadb.utils import embedding_functions


# 用 Chroma 内置的 sentence-transformers 做 embedding
ef = embedding_functions.DefaultEmbeddingFunction()

# 持久化存在本地 ./chroma_data 目录，重启不丢失
client = chromadb.PersistentClient(path="./chroma_data")


def get_collection(name: str = "investiq_news"):
    """
    获取或创建一个 collection
    collection 类似关系型数据库里的"表"，但存的是向量
    """
    return client.get_or_create_collection(
        name=name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}  # 用余弦相似度衡量语义距离
    )


def add_documents(texts: list[str], metadatas: list[dict], ids: list[str], collection_name: str = "investiq_news"):
    """
    把一批文本存入 Chroma
    
    texts     — 原始文本列表，Chroma 会自动转成向量
    metadatas — 每条文本的元信息，比如 {"source": "newsapi", "date": "2024-01-15", "ticker": "NVDA"}
    ids       — 每条文本的唯一ID，重复 ID 会覆盖旧数据
    """
    collection = get_collection(collection_name)
    collection.upsert(
        documents=texts,
        metadatas=metadatas,
        ids=ids
    )
    print(f"✓ 存入 {len(texts)} 条文本到 [{collection_name}]")


def query_documents(query: str, n_results: int = 5, collection_name: str = "investiq_news", where: dict = None):
    """
    语义检索：输入一段自然语言，返回最相关的几条文本
    
    query      — 查询语句，比如 "NVIDIA 数据中心业务增速放缓"
    n_results  — 返回几条结果
    where      — 元数据过滤，比如 {"ticker": "NVDA"} 只看 NVDA 的文章
    
    返回格式：
    [
        {"text": "...", "metadata": {...}, "distance": 0.12},
        ...
    ]
    """
    collection = get_collection(collection_name)
    
    kwargs = {"query_texts": [query], "n_results": n_results}
    if where:
        kwargs["where"] = where
    
    results = collection.query(**kwargs)
    
    # 把 Chroma 返回的嵌套格式拍平，方便使用
    output = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            output.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]  # 越小越相关
            })
    
    return output


# ── 直接运行这个文件就是做连通性测试 ──
if __name__ == "__main__":
    print("测试 Chroma 连接...")
    
    # 存一条测试数据
    add_documents(
        texts=["NVIDIA reported strong data center revenue growth in Q3 2024, driven by AI chip demand."],
        metadatas=[{"ticker": "NVDA", "source": "test", "date": "2024-01-01"}],
        ids=["test_001"]
    )
    
    # 用语义查询找到它
    results = query_documents("NVIDIA AI chip sales performance")
    print(f"\n查询结果（共 {len(results)} 条）：")
    for r in results:
        print(f"  距离: {r['distance']:.3f} | {r['text'][:80]}...")
    
    print("\n✓ Chroma 连通性测试通过")
