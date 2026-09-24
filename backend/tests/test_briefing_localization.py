from app.services.prematch_package import localize_briefing, parse_predictions_payload


def test_prediction_advice_and_winner_are_localized() -> None:
    parsed = parse_predictions_payload(
        {
            "response": [
                {
                    "predictions": {
                        "advice": "Double chance : draw or Germany",
                        "winner": {
                            "id": 25,
                            "name": "Germany",
                            "comment": "Win or draw",
                        },
                        "percent": {"home": "10%", "draw": "45%", "away": "45%"},
                    },
                    "comparison": {
                        "poisson_distribution": {"home": "47%", "away": "53%"}
                    },
                }
            ]
        }
    )

    assert parsed["advice"] == "双重机会：平局 或 德国"
    assert parsed["winner"]["name"] == "德国"
    assert parsed["winner"]["comment"] == "胜或平"
    assert parsed["comparison"][0]["label"] == "泊松分布"


def test_stored_combo_advice_is_localized_on_read() -> None:
    localized = localize_briefing(
        {
            "available": True,
            "advice": "Combo Winner : Germany and +1.5 goals",
            "winner": {"id": 25, "name": "Germany", "comment": "Winner"},
        }
    )

    assert localized["advice"] == "组合胜方：德国 且 总进球大于1.5"
    assert localized["winner"]["comment"] == "胜方"
