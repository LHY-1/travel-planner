from app.schemas.request import Weights
from app.schemas.domain import TransportOption, CityFeature


class ScoringService:
    @staticmethod
    def transport_penalty(option: TransportOption, weights: Weights) -> float:
        fatigue = option.transfer_count * 8 + max(0, option.duration_min - 180) / 60 * 5
        comfort_bonus = option.comfort_score * 10
        mode_bias = {
            "flight": -18,
            "train": -10,
            "bus": 22,
        }.get(option.mode, 0)
        return (
            weights.cost * option.price
            + weights.time * option.duration_min / 10
            + weights.fatigue * fatigue
            - weights.comfort * comfort_bonus
            + mode_bias
        )

    @staticmethod
    def city_gain(feature: CityFeature, weights: Weights) -> float:
        return (
            weights.experience * feature.experience_score
            - weights.cost * feature.hotel_cost
        )
