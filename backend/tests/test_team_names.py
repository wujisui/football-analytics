"""Regression tests pinning curated team ids to the right club.

Whole blocks of ``BY_ID`` were once curated against a wrong id list, so Holstein
Kiel showed up as "海登海姆", Köln as "圣保利" and Saint-Étienne as "巴黎FC".
``manage.py audit-team-names`` cross-checks the full table against the provider's
own labels; these tests pin the ids that actually burned a recommendation.
"""

from app.services.team_names import BY_ID, team_name_zh


def test_german_ids_match_official_clubs() -> None:
    expected = {
        174: "沙尔克04",
        175: "汉堡",
        176: "波鸿",
        178: "菲尔特",
        179: "马格德堡",
        180: "海登海姆",
        181: "达姆施塔特",
        183: "德累斯顿迪纳摩",
        186: "圣保利",
        188: "比勒费尔德",
        191: "霍尔施泰因基尔",
        192: "科隆",
    }
    for team_id, zh in expected.items():
        assert BY_ID[team_id] == zh, f"team {team_id} mistranslated"


def test_french_ids_match_official_clubs() -> None:
    expected = {
        93: "兰斯",
        94: "雷恩",
        99: "克莱蒙",
        106: "布雷斯特",
        114: "巴黎FC",
        1063: "圣埃蒂安",
    }
    for team_id, zh in expected.items():
        assert BY_ID[team_id] == zh, f"team {team_id} mistranslated"


def test_italian_and_spanish_ids_match_official_clubs() -> None:
    expected = {
        520: "克雷莫纳",
        801: "比萨",
        895: "科莫",
        539: "莱万特",
        718: "奥维耶多",
        726: "韦斯卡",
        9580: "布尔戈斯",
    }
    for team_id, zh in expected.items():
        assert BY_ID[team_id] == zh, f"team {team_id} mistranslated"


def test_reserve_and_friendly_ids_match_official_clubs() -> None:
    expected = {
        535: "马拉加",
        567: "比尔森胜利",
        9572: "赫塔费B队",
        9575: "皇马B队",
        9691: "埃尔切B队",
        19045: "亨克B队",
        19957: "鲁汶B队",
    }
    for team_id, zh in expected.items():
        assert BY_ID[team_id] == zh, f"team {team_id} mistranslated"


def test_ambiguous_short_names_resolve_by_id() -> None:
    # 3396 is AEL Limassol (Cyprus); 953 is AEL Larissa (Greece).
    assert team_name_zh("AEL", team_id=3396) == "利马索尔AEL"
    assert team_name_zh("AEL", team_id=953) == "拉里萨"
    # Al Ahly exists in several countries; the curated row is the Cairo club.
    assert BY_ID[1577] == "开罗阿赫利"


def test_brazilian_ids_are_not_french_clubs() -> None:
    assert BY_ID[129] == "塞阿拉"
    assert BY_ID[130] == "格雷米奥"


def test_no_duplicate_zh_name_inside_one_league_block() -> None:
    blocks = {
        "germany": [157, 159, 160, 161, 162, 163, 164, 165, 167, 168, 169, 170]
        + [172, 173, 174, 175, 176, 178, 179, 180, 181, 182, 183, 186]
        + [188, 191, 192, 744, 745, 785],
        "france": [77, 79, 80, 81, 82, 83, 84, 85, 91, 93, 94, 95, 96, 97, 99]
        + [106, 108, 111, 112, 114, 116, 1063],
        "italy": [487, 488, 489, 490, 492, 494, 495, 496, 497, 499, 500, 502]
        + [503, 504, 505, 520, 523, 801, 867, 895],
        "spain": [529, 530, 531, 532, 533, 536, 538, 539, 540, 541, 542, 543]
        + [544, 546, 547, 548, 715, 718, 720, 724, 726, 727, 728, 797, 798],
    }
    for label, ids in blocks.items():
        names = [BY_ID[team_id] for team_id in ids]
        assert len(names) == len(set(names)), f"duplicate name inside {label} block"


def test_ids_belonging_to_other_clubs_were_dropped() -> None:
    # 761 is Sporting CP B and 750 is Naftan; both were curated as European clubs.
    assert 761 not in BY_ID
    assert 750 not in BY_ID
    assert team_name_zh("Sporting CP B", team_id=761) == "Sporting CP B"


def test_id_wins_over_english_name() -> None:
    assert team_name_zh("Holstein Kiel", team_id=191) == "霍尔施泰因基尔"
    assert team_name_zh("1. FC Köln", team_id=192) == "科隆"
