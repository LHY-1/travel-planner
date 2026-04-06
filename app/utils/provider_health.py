from typing import Any, Dict, List, Tuple


def summarize_transport_matrix(matrix: Dict[Tuple[str, str], List[Any]]) -> Dict[str, Any]:
    pair_count = len(matrix)
    non_empty_pairs = sum(1 for _, v in matrix.items() if v)
    total_options = sum(len(v) for v in matrix.values())
    return {
        "pair_count": pair_count,
        "non_empty_pairs": non_empty_pairs,
        "total_options": total_options,
        "coverage": round(non_empty_pairs / pair_count, 4) if pair_count else 0,
    }
