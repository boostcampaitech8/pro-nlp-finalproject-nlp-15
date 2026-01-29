import argparse
import csv
import json
import os
from typing import Iterable, List, Dict, Any, Optional

import yaml
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


def load_config(config_path: str = "db.yaml") -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    qdrant_cfg = cfg.get("qdrant", {})
    insert_cfg = cfg.get("insert", {})
    run_cfg = cfg.get("run", {})

    return {
        "host": qdrant_cfg.get("host", "localhost"),
        "port": qdrant_cfg.get("port", 6333),
        "api_key": qdrant_cfg.get("api_key"),
        "prefer_grpc": qdrant_cfg.get("prefer_grpc", False),
        "https": qdrant_cfg.get("https", None),
        "timeout": qdrant_cfg.get("timeout", 60),
        "batch_size": insert_cfg.get("batch_size", 1000),
        "run": {
            "mode": run_cfg.get("mode"),
            "csv_path": run_cfg.get("csv_path"),
            "collection_name": run_cfg.get("collection_name"),
            "max_points": run_cfg.get("max_points"),
        },
    }


def init_qdrant_client(config: Dict[str, Any]) -> QdrantClient:
    return QdrantClient(
        host=config["host"],
        port=config["port"],
        api_key=config["api_key"],
        prefer_grpc=config["prefer_grpc"],
        https=config["https"],
        timeout=config["timeout"],
    )


def parse_embedding(raw: str) -> List[float]:
    """
    문자열로 저장된 임베딩을 List[float] 로 변환.
    예시 포맷:
      - "[0.1, 0.2, 0.3]"
      - "0.1,0.2,0.3"
      - "0.1 0.2 0.3"
    """
    if raw is None:
        raise ValueError("Embedding string is None")

    s = str(raw).strip()

    # JSON 리스트 형식인 경우
    if s.startswith("[") and s.endswith("]"):
        try:
            data = json.loads(s)
            return [float(x) for x in data]
        except Exception:
            # JSON 파싱 실패 시 아래 일반 파서로 재시도
            s = s[1:-1].strip()

    # 대괄호 제거 후, 쉼표 또는 공백 기준 split
    s = s.strip("[] \t\n\r")

    # 먼저 쉼표 기준 split, 쉼표가 없다면 공백 기준 split
    parts = s.split(",") if "," in s else s.split()
    return [float(p) for p in parts if p != ""]


def stream_csv_rows(csv_path: str) -> Iterable[Dict[str, Any]]:
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def prepare_collection(
    client: QdrantClient,
    collection_name: str,
    dim: int,
) -> None:
    """
    주어진 차원(dim)으로 컬렉션을 재생성(recreate)한다.
    이미 존재한다면 삭제 후 새로 만든다.
    """
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=dim,
            distance=Distance.COSINE,
        ),
    )


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    dim: int,
) -> int:
    """
    컬렉션이 없으면 생성하고, 현재 포인트 개수를 반환한다.
    resume 시 사용: 반환값만큼 CSV 행을 건너뛰고 이어서 넣으면 된다.
    """
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dim,
                distance=Distance.COSINE,
            ),
        )
        return 0
    info = client.get_collection(collection_name)
    return info.points_count


def infer_dimension_from_first_row(csv_path: str, embedding_key: str) -> int:
    """
    CSV 첫 번째 데이터 행에서 임베딩 차원을 추론.
    """
    for row in stream_csv_rows(csv_path):
        emb = parse_embedding(row[embedding_key])
        return len(emb)
    raise ValueError(f"No rows found in CSV: {csv_path}")


def load_article_collection(
    client: QdrantClient,
    csv_path: str,
    batch_size: int,
    collection_name: str = "article_v1",
    max_points: Optional[int] = None,
) -> None:
    """
    메인 기사 데이터셋을 article_v1 컬렉션에 적재.
    요구사항에 따라 point ID와 벡터(article_embedding)만 저장하고,
    나머지 컬럼은 payload에 넣지 않는다.
    """
    dim = infer_dimension_from_first_row(csv_path, "article_embedding")
    prepare_collection(client, collection_name, dim)

    batch: List[PointStruct] = []
    count = 0

    for row in stream_csv_rows(csv_path):
        if max_points is not None and count >= max_points:
            break

        point_id = int(row["id"])  # Qdrant에서 요구하는 unsigned integer ID
        vector = parse_embedding(row["article_embedding"])

        batch.append(PointStruct(id=point_id, vector=vector))

        if len(batch) >= batch_size:
            client.upsert(collection_name=collection_name, points=batch)
            count += len(batch)
            batch = []

    if batch:
        client.upsert(collection_name=collection_name, points=batch)
        count += len(batch)

    print(f"[{collection_name}] Upserted {count} points from {os.path.basename(csv_path)}")


def load_triple_collection(
    client: QdrantClient,
    csv_path: str,
    batch_size: int,
    collection_name: str = "triples_v1",
    max_points: Optional[int] = None,
    resume: bool = False,
) -> None:
    """
    트리플 임베딩 CSV를 triples_v1 컬렉션에 적재.
    예상 컬럼:
      - hash_id
      - embedding
      - triple_text

    Qdrant point ID는 0,1,2,... 와 같은 row index 기반 숫자를 사용하고,
    hash_id / triple_text 는 payload 로만 저장한다.

    resume=True 이면 컬렉션을 지우지 않고, 이미 들어간 개수만큼 CSV를 건너뛴 뒤 이어서 넣는다.
    """
    dim = infer_dimension_from_first_row(csv_path, "embedding")
    if resume:
        start_id = ensure_collection(client, collection_name, dim)
        if start_id > 0:
            print(f"[{collection_name}] Resume: skipping first {start_id} rows, appending from row index {start_id}.")
    else:
        prepare_collection(client, collection_name, dim)
        start_id = 0

    batch: List[PointStruct] = []
    count = 0
    row_index = 0

    for row in stream_csv_rows(csv_path):
        if row_index < start_id:
            row_index += 1
            continue
        if max_points is not None and count >= max_points:
            break

        point_id = row_index  # 0,1,2,... (resume 시 start_id, start_id+1, ...)
        vector = parse_embedding(row["embedding"])

        payload = {
            "hash_id": row.get("hash_id"),
            "triple_text": row.get("triple_text"),
        }

        batch.append(PointStruct(id=point_id, vector=vector, payload=payload))
        row_index += 1

        if len(batch) >= batch_size:
            client.upsert(collection_name=collection_name, points=batch)
            count += len(batch)
            batch = []

    if batch:
        client.upsert(collection_name=collection_name, points=batch)
        count += len(batch)

    print(f"[{collection_name}] Upserted {count} points from {os.path.basename(csv_path)}")


def load_entity_collection(
    client: QdrantClient,
    csv_path: str,
    batch_size: int,
    collection_name: str = "entity_v1",
    max_points: Optional[int] = None,
    resume: bool = False,
) -> None:
    """
    엔티티 임베딩 CSV를 entity_v1 컬렉션에 적재.
    예상 컬럼:
      - hash_id
      - embedding
      - entity_text

    Qdrant point ID는 0,1,2,... 와 같은 row index 기반 숫자를 사용하고,
    hash_id / entity_text 는 payload 로만 저장한다.

    resume=True 이면 컬렉션을 지우지 않고, 이미 들어간 개수만큼 CSV를 건너뛴 뒤 이어서 넣는다.
    """
    dim = infer_dimension_from_first_row(csv_path, "embedding")
    if resume:
        start_id = ensure_collection(client, collection_name, dim)
        if start_id > 0:
            print(f"[{collection_name}] Resume: skipping first {start_id} rows, appending from row index {start_id}.")
    else:
        prepare_collection(client, collection_name, dim)
        start_id = 0

    batch: List[PointStruct] = []
    count = 0
    row_index = 0

    for row in stream_csv_rows(csv_path):
        if row_index < start_id:
            row_index += 1
            continue
        if max_points is not None and count >= max_points:
            break

        point_id = row_index  # 0,1,2,... (resume 시 start_id, start_id+1, ...)
        vector = parse_embedding(row["embedding"])

        payload = {
            "hash_id": row.get("hash_id"),
            "entity_text": row.get("entity_text"),
        }

        batch.append(PointStruct(id=point_id, vector=vector, payload=payload))
        row_index += 1

        if len(batch) >= batch_size:
            client.upsert(collection_name=collection_name, points=batch)
            count += len(batch)
            batch = []

    if batch:
        client.upsert(collection_name=collection_name, points=batch)
        count += len(batch)

    print(f"[{collection_name}] Upserted {count} points from {os.path.basename(csv_path)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert CSV data into Qdrant VectorDB.")
    parser.add_argument(
        "--mode",
        required=False,
        choices=["article", "triple", "entity"],
        help="어떤 컬렉션에 넣을지 선택 (article / triple / entity). 지정 안 하면 db.yaml(run.mode) 사용.",
    )
    parser.add_argument(
        "--csv-path",
        required=False,
        help="입력 CSV 파일 경로. 지정 안 하면 db.yaml(run.csv_path) 사용.",
    )
    parser.add_argument(
        "--config",
        default="db.yaml",
        help="Qdrant 설정이 들어있는 YAML 파일 경로 (기본: db.yaml)",
    )
    parser.add_argument(
        "--collection-name",
        default=None,
        help="Qdrant 컬렉션 이름 (기본: article_v1 / triples_v1 / entity_v1). 지정 안 하면 db.yaml(run.collection_name) 또는 기본값 사용.",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=None,
        help="최대 업서트할 포인트 개수 (예: 3000). 지정 안 하면 db.yaml(run.max_points) 또는 전체 업서트.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="triple/entity 모드: 컬렉션을 비우지 않고, 이미 들어간 개수만큼 CSV를 건너뛴 뒤 이어서 넣는다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cfg = load_config(args.config)
    client = init_qdrant_client(cfg)

    run_cfg = cfg.get("run", {})

    # CLI 인자가 있으면 우선, 없으면 db.yaml(run.*) 사용
    mode = args.mode or run_cfg.get("mode")
    csv_path = args.csv_path or run_cfg.get("csv_path")
    batch_size = cfg["batch_size"]
    max_points = args.max_points if args.max_points is not None else run_cfg.get("max_points")

    if mode is None:
        raise ValueError("mode 가 지정되지 않았습니다. --mode 인자나 db.yaml 의 run.mode 를 설정하세요.")
    if not csv_path:
        raise ValueError("csv_path 가 지정되지 않았습니다. --csv-path 인자나 db.yaml 의 run.csv_path 를 설정하세요.")

    if mode == "article":
        collection_name = args.collection_name or run_cfg.get("collection_name") or "article_v1"
        load_article_collection(
            client,
            csv_path,
            batch_size,
            collection_name,
            max_points=max_points,
        )
    elif mode == "triple":
        collection_name = args.collection_name or run_cfg.get("collection_name") or "triples_v1"
        load_triple_collection(
            client,
            csv_path,
            batch_size,
            collection_name,
            max_points=max_points,
            resume=args.resume,
        )
    elif mode == "entity":
        collection_name = args.collection_name or run_cfg.get("collection_name") or "entity_v1"
        load_entity_collection(
            client,
            csv_path,
            batch_size,
            collection_name,
            max_points=max_points,
            resume=args.resume,
        )
    else:
        raise ValueError(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
