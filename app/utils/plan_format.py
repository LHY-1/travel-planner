from app.schemas.response import PlanOption, Segment


def build_option(result: dict, provider_name: str, pace: str) -> PlanOption:
    segments = result.get('segments', [])
    return PlanOption(
        route=result['route'],
        total_cost=result['total_cost'],
        total_experience=result['total_experience'],
        total_time_min=result['total_time_min'],
        total_score=result['total_score'],
        segments=[
            Segment(
                from_city=s.from_city,
                to_city=s.to_city,
                mode=s.mode,
                price=s.price,
                duration_min=s.duration_min,
                score=0,
            ) for s in segments
        ],
        meta={
            "provider": provider_name,
            "pace": pace,
            "strategy": result.get("strategy", "dp"),
            "segment_modes": [getattr(s, 'mode', '-') for s in segments],
        },
    )
