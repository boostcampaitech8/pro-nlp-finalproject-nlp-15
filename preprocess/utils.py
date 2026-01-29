from hashlib import md5

def compute_mdhash_id(content: str, prefix: str = "") -> str:
    return prefix + md5(content.encode()).hexdigest()

def compute_hash(object_list: str, prefix: str = "E") -> str:
    """
    엔티티/트리플 텍스트에서 md5 기반 hash_id 생성.

    prefix:
      - "E" -> entity-<md5>
      - "T" -> triple-<md5>
    """
    if prefix == "E":
        # 엔티티 해쉬
        entity = str(object_list).strip()
        return compute_mdhash_id(entity, prefix="entity-")

    if prefix == "T":
        # 트리플 해쉬
        triple_text = str(object_list).strip()
        return compute_mdhash_id(triple_text, prefix="triple-")

    # 그 외 prefix 는 그냥 그대로 붙여서 반환
    return compute_mdhash_id(str(object_list).strip(), prefix=f"{prefix}-")
