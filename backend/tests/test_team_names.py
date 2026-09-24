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


def test_prematch_window_ids_match_official_clubs() -> None:
    expected = {
        575: "雅典AEK",
        998: "特拉布宗体育",
        279: "札幌冈萨多",
        10307: "乌拉圭U20",
        16202: "巴拉圭U20",
        1564: "泰国",
        2691: "凯泽酋长",
        1051: "特古西加尔帕奥林匹亚",
    }
    for team_id, zh in expected.items():
        assert BY_ID[team_id] == zh, f"team {team_id} mistranslated"


def test_hot_league_missing_names_match_official_clubs() -> None:
    """Pin representative ids from the 2026-09-21 hot-league backfill."""
    expected = {
        14: "塞尔维亚",
        185: "帕德博恩",
        550: "顿涅茨克矿工",
        946: "纽卡斯尔喷气机",
        2523: "柔佛新山",
        2733: "德黑兰独立",
        2870: "迪拜阿赫利",
        2872: "瓦斯尔",
        4217: "涅夫奇",
        8009: "巴格达空军",
        16078: "汉堡HEBC",
    }
    for team_id, zh in expected.items():
        assert BY_ID[team_id] == zh, f"team {team_id} mistranslated"


def test_spanish_names_use_mainland_transliteration() -> None:
    """西甲段统一大陆译名，不能混进港台译法。

    533 一度写成「维拉利尔」（港台），而同段的巴列卡诺 / 加的斯 / 巴拉多利德
    全是大陆标准译名。``audit-team-names`` 查不出这类问题：它比对的是 ``BY_ID``
    与 ``BY_NAME`` 是否指向同一家俱乐部，两处风格一起写错时不会报冲突。
    """
    assert BY_ID[533] == "比利亚雷亚尔"
    assert team_name_zh("Villarreal") == "比利亚雷亚尔"


def test_new_hot_leagues_use_verified_ids() -> None:
    """亚运 / 墨西哥联 / 哥伦甲 按官方 id 写，男足国家队与女足 / U23 不能串。"""
    assert BY_ID[1566] == "中国"
    assert BY_ID[1723] == "中国女足"
    assert BY_ID[10932] == "中国U23"
    assert BY_ID[2287] == "美洲队"
    assert BY_ID[2295] == "蓝十字"
    assert BY_ID[1131] == "布卡拉曼加"
    assert team_name_zh("China PR U23", team_id=10932) == "中国U23"
    assert team_name_zh("China W", team_id=1723) == "中国女足"


def test_hot_friendly_leagues_include_youth_national_sides() -> None:
    """国际友谊赛是热门联赛，里面的 U17/U18/U19/U21 也在译名范围内。

    规则排除的是*非热门*联赛的青年队；`leagues.is_hot=true` 的友谊赛曾被整段跳过。
    """
    assert BY_ID[8194] == "法国U21"
    assert BY_ID[10332] == "英格兰U19"
    assert BY_ID[17949] == "英格兰U17"
    assert BY_ID[21460] == "奥地利U18"
    assert team_name_zh("Republic of Ireland U19", team_id=10377) == "爱尔兰U19"
    # 成年队与各年龄段互不覆盖。
    assert BY_ID[10] == "英格兰"
    assert BY_ID[2] == "法国"


def test_uwcl_and_new_window_ids_match_official_clubs() -> None:
    """女足欧冠与 9/23 新赛程按官方 id 写，女足不能写成男足简称。"""
    assert BY_ID[1850] == "阿森纳女足"
    assert BY_ID[1667] == "巴黎女足"
    assert BY_ID[1676] == "巴黎FC女足"
    assert BY_ID[1918] == "巴萨女足"
    assert BY_ID[7533] == "国际米兰女足"
    assert BY_ID[1912] == "皇家社会女足"
    assert team_name_zh("Arsenal W", team_id=1850) == "阿森纳女足"
    assert BY_ID[42] == "阿森纳"
    assert BY_ID[21466] == "英格兰U18"
    assert BY_ID[10] == "英格兰"
    assert BY_ID[1494] == "圣多美和普林西比"


def test_afcon_qualification_ids_match_official_nations() -> None:
    """非洲杯预选赛按官方 team id 写，刚果（金）/ 刚果（布）不能串。"""
    assert BY_ID[19] == "尼日利亚"
    assert BY_ID[1508] == "刚果（金）"
    assert BY_ID[1517] == "刚果（布）"
    assert BY_ID[1513] == "几内亚比绍"
    assert BY_ID[1496] == "南苏丹"
    assert BY_ID[8050] == "索马里"
    assert team_name_zh("Nigeria", team_id=19) == "尼日利亚"
    assert team_name_zh("Congo", team_id=1517) == "刚果（布）"
    assert team_name_zh("Congo DR", team_id=1508) == "刚果（金）"


def test_a_league_ids_are_not_german_club_188() -> None:
    """澳超是联赛 id 188；球队 id 188 是比勒费尔德，不能按联赛号猜队。"""
    assert BY_ID[188] == "比勒费尔德"
    assert BY_ID[941] == "中岸水手"
    assert BY_ID[942] == "惠灵顿凤凰"
    assert BY_ID[943] == "悉尼FC"
    assert BY_ID[944] == "墨尔本胜利"
    assert BY_ID[947] == "布里斯班狮吼"
    assert team_name_zh("Sydney", team_id=943) == "悉尼FC"
    assert team_name_zh("Melbourne Victory", team_id=944) == "墨尔本胜利"
    assert team_name_zh("Melbourne City", team_id=945) == "墨尔本城"



def test_hot_efl_trophy_and_youth_ids_match_official_clubs() -> None:
    """英锦联与热门友谊赛/亚运缺译名按官方 id 补，不能串到同名成年队。"""
    expected = {
        4: "俄罗斯",
        61: "维冈",
        74: "谢周三",
        1348: "米尔顿凯恩斯",
        1356: "布莱克浦",
        5531: "多米尼克",
        7196: "利物浦U21",
        8150: "安圭拉",
        10177: "韩国U23",
        10955: "沙特U23",
        12522: "美国U17",
        12786: "泽伦多夫赫塔",
        25282: "美国U19",
    }
    for team_id, zh in expected.items():
        assert BY_ID[team_id] == zh, f"team {team_id} mistranslated"
    assert team_name_zh("Korea Republic U23", team_id=10177) == "韩国U23"
    assert team_name_zh("Liverpool U21", team_id=7196) == "利物浦U21"
    assert BY_ID[40] == "利物浦"
    assert BY_ID[17] == "韩国"


def test_arabic_club_names_are_transliterated_not_glossed() -> None:
    """阿拉伯语队名按音译或沿用既有「城市+阿赫利」格式，不做字面意译。

    Al-Wasl 曾被写成「迪拜祈祷」——与原词毫无关系；Shabab Al Ahli 曾按字面拆成
    「迪拜青年国民」，而库里同源俱乐部用的是 开罗阿赫利 / 吉达阿赫利。
    """
    assert BY_ID[2872] == "瓦斯尔"
    assert BY_ID[2870] == "迪拜阿赫利"
    assert BY_ID[1577] == "开罗阿赫利"
    assert BY_ID[2929] == "吉达阿赫利"


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
