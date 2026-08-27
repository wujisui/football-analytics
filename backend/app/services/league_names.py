"""API-Sports league id / English name → 中文 display name.

Single source of truth (mirrors ``team_names.py``):
- ingest / sync (``FootballFetcher._upsert_league``)
- list & detail APIs (``fixtures._league_name``)
- filter options (``leagues._name``)
- form / H2H match rows (``localize_match_row``)
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings

# English names shared by many countries — never default to a major league without country.
_NEEDS_COUNTRY = frozenset(
    {
        "Premier League",
        "Pro League",
        "Serie A",
        # Germany + Austria both call their top flight "Bundesliga".
        "Bundesliga",
        "2. Liga",
        # England and Scotland both have a competition named "Championship".
        "Championship",
        "Super League",
        "FA Cup",
        "League One",
        "League Two",
        "Liga Pro",
        "First Division",
        "Second Division",
    }
)

# Only globally unambiguous English API names belong here. Domestic/generic
# competition names must use ``_BY_NAME_COUNTRY`` or ``_BY_ID``.
_BY_UNAMBIGUOUS_NAME: dict[str, str] = {
    "EFL Cup": "英联杯",
    "La Liga": "西甲",
    "Copa Del Rey": "国王杯",
    "ASEAN Championship": "东南亚锦标赛",
    "Asean Championship Women": "东南亚女足锦标赛",
    "Superettan": "瑞典甲",
    "Svenska Cupen": "瑞典杯",
    "Damallsvenskan": "瑞典女超",
    "Elitettan": "瑞典女甲",
    "Ykkönen": "芬甲",
    "Ykkösliiga": "芬K2",
    "Kansallinen Liiga": "芬兰女超",
    "NWSL Women": "美女职",
    "USL Championship": "美冠联",
    "USL League Two": "美业余联",
    "USL League One": "美职联三级",
    "MLS Next Pro": "美职预备联",
    "Süper Lig": "土超",
    "Veikkausliiga": "芬超",
    "Ekstraklasa": "波超",
    "Copa Do Brasil": "巴西杯",
    "Copa Chile": "智利杯",
    "Jupiler Pro League": "比甲",
    "Liga MX": "墨超",
    "Liga MX Femenil": "墨超女足",
    "NB I": "匈甲",
    "HNL": "克罗地亚甲",
    "Czech Liga": "捷甲",
    "Meistaradeildin": "法罗超",
    "Leagues Cup": "美墨联赛杯",
    "Piala Presiden": "印尼总统杯",
    "Canadian Premier League": "加超",
    "Northern Super League": "加女超",
    "UEFA Champions League Women": "女足欧冠",
    "CONCACAF U20": "中北美U20",
    "Friendlies Women": "女足友谊赛",
    "K League 2": "韩K2",
    "K3 League": "韩K3",
    "K4 League": "韩K4",
    "WK-League": "韩女联",
    "NB II": "匈乙",
    "Botola 2": "摩洛乙",
    "Challenge League": "瑞士挑战联",
    "Esiliiga A": "爱沙乙",
    "Meistriliiga": "爱沙超",
    "Esiliiga B": "爱沙丙",
    "Virsliga": "拉脱超",
    "Persha Liga": "乌克乙",
    "FNL": "捷乙",
    "1. SNL": "斯洛文甲",
    "Liga de Expansión MX": "墨扩军联",
    "Liga MX U21": "墨U21联",
    "Australia Cup": "澳大利亚杯",
    "Premier League - Summer Series": "英超夏季系列赛",
    "Coppa Italia": "意大利杯",
    "2. Bundesliga": "德乙",
    "DFB Pokal": "德国杯",
    "Ligue 1": "法甲",
    "Ligue 2": "法乙",
    "Coupe de France": "法国杯",
    "Eredivisie": "荷甲",
    "Eerste Divisie": "荷乙",
    "Primeira Liga": "葡超",
    "UEFA Champions League": "欧冠",
    "UEFA Europa League": "欧罗巴",
    "UEFA Europa Conference League": "欧协联",
    "UEFA Super Cup": "欧洲超级杯",
    "AFC Champions League": "亚冠",
    "AFC Champions League Elite": "亚冠精英",
    "AFC Champions League Two": "亚冠二级",
    "World Cup": "世界杯",
    "Euro Championship": "欧洲杯",
    "Africa Cup of Nations": "非洲杯",
    "Copa America": "美洲杯",
    "Confederations Cup": "联合会杯",
    "Friendlies": "友谊赛",
    "Friendlies Clubs": "俱乐部友谊赛",
    "Club Friendlies": "俱乐部友谊赛",
    "World Cup - Qualification Europe": "世预赛(欧)",
    "World Cup - Qualification Africa": "世预赛(非)",
    "World Cup - Qualification South America": "世预赛(南美)",
    "World Cup - Qualification Asia": "世预赛(亚)",
    "UEFA Nations League": "欧国联",
    "Scottish Premiership": "苏超",
    "Super Lig": "土超",
    "Saudi Pro League": "沙特联",
    "Major League Soccer": "美职联",
    "MLS": "美职联",
    "Brazil Serie A": "巴甲",
    "Serie A - Brazil": "巴甲",
    "A-League": "澳超",
    "J1 League": "日职联",
    "K League 1": "韩K联",
    "Chinese Super League": "中超",
    "China League One": "中甲",
    "China League Two": "中乙",
    "CFA": "中协杯",
    "Chinese FA Cup": "中协杯",
    "1 Lyga": "立甲",
    "A Lyga": "立乙",
    "Calcutta Premier A Division": "加尔各答超A组",
    "Calcutta Premier Division": "加尔各答超",
    "I-League": "印度I联赛",
    # 名称本身已锁定国家/组织，不会跨国复用
    "Emperor Cup": "天皇杯",
    "DBU Pokalen": "丹麦杯",
    "Copa Argentina": "阿根廷杯",
    "Cupa României": "罗马尼亚杯",
    "Copa Paraguay": "巴拉圭杯",
    "Copa Ecuador": "厄瓜多尔杯",
    "Copa Venezuela": "委内瑞拉杯",
    "Persian Gulf Pro League": "伊朗超",
    "Ligi kuu Bara": "坦桑尼亚超",
    "CONCACAF Central American Cup": "中北美中美洲杯",
    "OFC Champions League": "大洋洲冠军联赛",
}

# ``name|country`` as returned by API-Sports.
_BY_NAME_COUNTRY: dict[str, str] = {
    "Bundesliga|Germany": "德甲",
    "Bundesliga|Austria": "奥超",
    "2. Liga|Austria": "奥乙",
    "Championship|England": "英冠",
    "Championship|Scotland": "苏冠",
    "Championship|Northern-Ireland": "北爱冠",
    "Championship|Northern Ireland": "北爱冠",
    "Premier League|England": "英超",
    "Premier League|Russia": "俄超",
    "Premier League|Ukraine": "乌克超",
    "Premier League|Kyrgyzstan": "吉尔吉斯超",
    "Premier League|Malta": "马耳他超",
    "Premier League|Israel": "以超",
    "Premier League|Wales": "威超",
    "Premier League|Uganda": "乌干达超",
    "Premier League|Bahrain": "巴林超",
    "Premier League|Bangladesh": "孟加拉超",
    "Premier League|Ghana": "加纳超",
    "Premier League|Libya": "利比亚超",
    "Premier League|Kuwait": "科威特超",
    "Premier League|Hong-Kong": "港超",
    "Premier League|Hong Kong": "港超",
    "Premier League|Singapore": "新加坡超",
    "Premier League|Jamaica": "牙买加超",
    "Premier League|Trinidad-And-Tobago": "特立尼达超",
    "Premier League|Trinidad And Tobago": "特立尼达超",
    "League One|China": "中甲",
    "League Two|China": "中乙",
    "Super League|China": "中超",
    "Super League|Uzbekistan": "乌兹超",
    "Super League|Switzerland": "瑞士超",
    "Super League|Greece": "希腊超",
    "FA Cup|China": "中协杯",
    "FA Cup|England": "英足总杯",
    "FA Cup|South-Korea": "韩国杯",
    "FA Cup|South Korea": "韩国杯",
    "Korea Cup|South-Korea": "韩国杯",
    "Korea Cup|South Korea": "韩国杯",
    "Serie A|Brazil": "巴甲",
    "Serie A|Italy": "意甲",
    "Serie B|Italy": "意乙",
    "League One|England": "英甲",
    "League One|Scotland": "苏甲",
    "League Two|England": "英乙",
    "League Two|Scotland": "苏乙",
    "Pro League|Belgium": "比甲",
    "Pro League|Saudi-Arabia": "沙特联",
    "Pro League|Saudi Arabia": "沙特联",
    "Liga Pro|Ecuador": "厄甲",
    "Primera División|Bolivia": "玻利甲",
    "Division Profesional|Bolivia": "玻利甲",
    "First Division|Ireland": "爱甲",
    "Premier Division|Ireland": "爱超",
    "Segunda División|Spain": "西乙",
    "Segunda División|Chile": "智利乙",
    "Segunda División|Uruguay": "乌拉乙",
    "Segunda División|Venezuela": "委内乙",
    "Primera División|Chile": "智利甲",
    "Primera División|Uruguay": "乌拉甲",
    "Primera División|Venezuela": "委内甲",
    "Primera Division|El-Salvador": "萨尔瓦多甲",
    "Primera Division|El Salvador": "萨尔瓦多甲",
    "Liga Nacional|Honduras": "洪都拉斯甲",
    "Liga Nacional|Guatemala": "危地马拉甲",
    "Superliga|Denmark": "丹超",
    "Super Liga|Serbia": "塞超",
    "1. Deild|Faroe-Islands": "法罗甲",
    "1. Deild|Faroe Islands": "法罗甲",
    "First League|Montenegro": "黑山超",
    "Cup|Poland": "波兰杯",
    "2. Division|Denmark": "丹乙",
    "3. Division|Denmark": "丹丙",
    "Serie B|Brazil": "巴乙",
    "Serie C|Brazil": "巴丙",
    "Serie D|Brazil": "巴丁",
    "1. Division|Norway": "挪甲",
    "1. Division|Belarus": "白俄甲",
    "1. Division|Denmark": "丹甲",
    "1. Division|Kazakhstan": "哈萨克甲",
    "I Liga|Poland": "波乙",
    "II Liga - East|Poland": "波丙(东)",
    "Primera Nacional|Argentina": "阿乙",
    "Primera B Metropolitana|Argentina": "阿丙(大都会)",
    "Primera C|Argentina": "阿丁",
    "Torneo Federal A|Argentina": "阿根廷联邦A",
    "Primera División|Costa-Rica": "哥斯达黎加甲",
    "Primera División|Peru": "秘鲁甲",
    "Primera B|Colombia": "哥伦乙",
    "Primera B|Chile": "智利乙",
    "Primera B|Peru": "秘鲁乙",
    "Copa Colombia|Colombia": "哥伦杯",
    "Liga Pro Serie B|Ecuador": "厄乙",
    "Second League|Bulgaria": "保乙",
    "First League|Bulgaria": "保超",
    "First League|Russia": "俄甲",
    "Youth Championship|Russia": "俄青联",
    "League Cup|Scotland": "苏格兰联赛杯",
    "Cup|Iceland": "冰岛杯",
    "Cup|Austria": "奥地利杯",
    "Cup|Estonia": "爱沙杯",
    "Cup|Czech-Republic": "捷克杯",
    "Úrvalsdeild|Iceland": "冰岛超",
    "1. Deild|Iceland": "冰岛甲",
    "2. Deild|Iceland": "冰岛乙",
    "Division Profesional - Clausura|Paraguay": "巴拉甲",
    "Division Intermedia|Paraguay": "巴拉乙",
    "Premier League|Kazakhstan": "哈萨克超",
    "Premier League|Lebanon": "黎巴嫩超",
    "Premier League|Bhutan": "不丹超",
    "Super League|Malawi": "马拉维超",
    "Super Liga|Slovakia": "斯洛伐克超",
    "Super Liga|Moldova": "摩尔多瓦超",
    "Premier Soccer League|Zimbabwe": "津巴布韦超",
    "Primera Division|Nicaragua": "尼加拉瓜甲",
    "Division 1|Kuwait": "科威特甲",
    "First League|Macedonia": "北马其甲",
    "FAI Cup|Ireland": "爱足总杯",
    "Primeira Divisão|Macao": "澳门甲",
    "Premier League|Belarus": "白俄超",
    "Premier League|Armenia": "亚美尼亚超",
    "Primera A|Colombia": "哥伦甲",
    "Ligue A|Burundi": "布隆迪甲",
    "Stars League|Qatar": "卡塔尔星联",
    "Premier Soccer League|South-Africa": "南非超",
    "Premier Soccer League|South Africa": "南非超",
    # 泰国也有 King's Cup，必须按国家区分
    "King's Cup|Saudi-Arabia": "沙特国王杯",
    "King's Cup|Saudi Arabia": "沙特国王杯",
    "Cup|Greece": "希腊杯",
    "Cup|Russia": "俄罗斯杯",
    "Cup|Kazakhstan": "哈萨克杯",
    "Cup|Slovakia": "斯洛伐克杯",
}

# Any name with a country-specific translation is country-scoped by default.
# This turns disambiguation into the safe default: without a stable league ID
# or matching country, preserve the official name instead of guessing.
_COUNTRY_SCOPED_NAMES = frozenset(
    {
        *_NEEDS_COUNTRY,
        *(key.rsplit("|", 1)[0] for key in _BY_NAME_COUNTRY),
    }
)
assert _COUNTRY_SCOPED_NAMES.isdisjoint(_BY_UNAMBIGUOUS_NAME), (
    "Country-scoped league names must not appear in the pure-name translation map"
)

# Observed in local DB / API discovery — id wins over stale or wrong stored labels.
_BY_ID: dict[int, str] = {
    24: "东南亚锦标赛",
    27: "大洋洲冠军联赛",
    40: "英冠",
    43: "英全国联",
    50: "英全国联北",
    51: "英全国联南",
    58: "英依斯米安超",
    59: "英北部超",
    60: "英南部超(南)",
    62: "法乙",
    63: "法丙",
    72: "巴乙",
    73: "巴西杯",
    74: "巴女甲",
    75: "巴丙",
    76: "巴丁",
    78: "德甲",
    79: "德乙",
    80: "德丙",
    83: "德地区拜仁",
    84: "德地区北",
    85: "德地区东北",
    86: "德地区西南",
    87: "德地区西",
    88: "荷甲",
    89: "荷乙",
    94: "葡超",
    95: "葡甲",
    100: "日丙",
    102: "天皇杯",
    104: "挪甲",
    106: "波超",
    107: "波乙",
    108: "波兰杯",
    109: "波丙(东)",
    111: "威甲",
    114: "瑞典甲",
    115: "瑞典杯",
    116: "白俄超",
    117: "白俄甲",
    119: "丹超",
    120: "丹甲",
    121: "丹麦杯",
    122: "丹乙",
    129: "阿乙",
    130: "阿根廷杯",
    131: "阿丙(大都会)",
    132: "阿丁",
    134: "阿根廷联邦A",
    144: "比甲",
    162: "哥斯达黎加甲",
    163: "哥斯达黎加乙",
    164: "冰岛超",
    165: "冰岛甲",
    166: "冰岛乙",
    167: "冰岛杯",
    170: "中甲",
    171: "中协杯",
    172: "保超",
    173: "保乙",
    179: "苏超",
    180: "苏冠",
    183: "苏甲",
    184: "苏乙",
    185: "苏格兰联赛杯",
    189: "澳首都NPL",
    192: "新南威尔士NPL",
    194: "南澳NPL",
    195: "维多利亚NPL",
    196: "西澳NPL",
    199: "希腊杯",
    201: "摩洛乙",
    203: "土超",
    204: "土甲",
    208: "瑞士挑战联",
    210: "克罗地亚甲",
    218: "奥超",
    219: "奥乙",
    220: "奥地利杯",
    221: "奥地区东",
    234: "洪都拉斯甲",
    235: "俄超",
    236: "俄甲",
    237: "俄罗斯杯",
    238: "俄青联",
    239: "哥伦甲",
    240: "哥伦乙",
    241: "哥伦杯",
    243: "厄乙",
    244: "芬超",
    245: "芬甲",
    247: "芬丙A组",
    248: "芬丙B组",
    249: "芬丙C组",
    251: "巴拉乙",
    252: "巴拉甲",
    254: "美女职",
    255: "美冠联",
    256: "美业余联",
    261: "卢森堡甲",
    262: "墨超",
    263: "墨扩军联",
    265: "智利甲",
    266: "智利乙",
    267: "智利杯",
    268: "乌拉甲",
    269: "乌拉乙",
    271: "匈甲",
    272: "匈乙",
    282: "秘鲁乙",
    283: "罗甲",
    284: "罗乙",
    285: "罗马尼亚杯",
    286: "塞超",
    287: "塞甲",
    288: "南非超",
    290: "伊朗超",
    293: "韩K2",
    294: "韩国杯",
    295: "韩K3",
    299: "委内甲",
    300: "委内乙",
    304: "巴拿马甲",
    305: "卡塔尔星联",
    315: "波黑超",
    326: "格鲁吉亚甲",
    327: "格鲁吉亚超",
    328: "爱沙乙",
    329: "爱沙超",
    331: "科威特甲",
    332: "斯洛伐克超",
    333: "乌克超",
    334: "乌克乙",
    339: "危地马拉甲",
    342: "亚美尼亚超",
    345: "捷甲",
    346: "捷乙",
    347: "捷克杯",
    348: "捷丙CFL A",
    349: "捷丙MSFL",
    350: "捷丁A",
    352: "捷丁C",
    353: "捷丁D",
    354: "捷丁E",
    355: "黑山超",
    357: "爱超",
    358: "爱甲",
    359: "爱足总杯",
    364: "拉脱甲",
    365: "拉脱超",
    366: "法罗甲",
    367: "法罗超",
    370: "萨尔瓦多甲",
    371: "北马其甲",
    373: "斯洛文甲",
    374: "斯洛文乙",
    385: "以色列图图杯",
    388: "哈萨克甲",
    389: "哈萨克超",
    390: "黎巴嫩超",
    391: "马拉维超",
    394: "摩尔多瓦超",
    396: "尼加拉瓜甲",
    401: "津巴布韦超",
    407: "北爱冠",
    408: "北爱超",
    473: "挪丙1组",
    474: "挪丙2组",
    479: "加超",
    481: "北新南威尔士NPL",
    482: "昆士兰NPL",
    484: "奥女甲",
    486: "白俄杯",
    489: "美职联三级",
    498: "哈萨克杯",
    501: "巴拉圭杯",
    504: "沙特国王杯",
    506: "斯洛伐克乙",
    509: "南非8强杯",
    510: "瑞士晋级联",
    525: "女足欧冠",
    537: "中北美U20",
    549: "瑞典女超",
    563: "瑞典乙北",
    564: "瑞典乙南",
    566: "布隆迪甲",
    567: "坦桑尼亚超",
    569: "吉尔吉斯超",
    592: "瑞典丙西约塔北",
    593: "瑞典丙斯维兰北",
    594: "瑞典丙诺尔兰",
    595: "瑞典丙斯维兰南",
    596: "瑞典丙西约塔西",
    597: "瑞典丙南约塔",
    613: "巴亚二",
    619: "米内罗二",
    633: "匈丙(东北)",
    634: "匈丙(西南)",
    635: "匈丙(西北)",
    638: "丹麦女超",
    640: "芬兰女超",
    645: "斯洛伐克丙(东)",
    648: "塔斯马尼亚NPL",
    650: "俄乙3组",
    651: "俄乙1组",
    652: "俄乙2组",
    653: "俄乙4组",
    657: "爱沙杯",
    660: "韩女联",
    666: "女足友谊赛",
    668: "捷U19甲",
    672: "格鲁吉亚杯",
    673: "墨超女足",
    680: "斯洛伐克杯",
    685: "捷丙CFL B",
    711: "智利乙",
    712: "哥伦女甲",
    730: "苏高地联",
    731: "苏低地联",
    736: "瑞典女甲",
    740: "巴U20A",
    742: "圣保罗杯",
    745: "德业余汉堡",
    772: "美墨联赛杯",
    774: "挪丁1组",
    775: "挪丁2组",
    776: "挪丁3组",
    777: "挪丁4组",
    778: "挪丁5组",
    779: "挪丁6组",
    780: "波丁1组",
    781: "波丁2组",
    782: "波丁3组",
    783: "波丁4组",
    810: "阿超杯",
    823: "挪U19冠军杯",
    833: "昆士兰超级联",
    834: "南澳州联1",
    835: "新南威尔士NPL2",
    836: "维多利亚NPL2",
    856: "中北美加勒比俱乐部锦标赛",
    862: "丹丙",
    865: "葡丙",
    869: "东非俱乐部杯",
    874: "澳大利亚杯",
    906: "阿预备联",
    909: "美职预备联",
    917: "厄瓜多尔杯",
    924: "印尼总统杯",
    929: "中乙",
    931: "英南部超(中)",
    936: "卡德里二",
    938: "德业余拜仁北",
    939: "德业余拜仁南",
    969: "澳门甲",
    1016: "中美洲及加勒比运动会",
    1022: "英超夏季系列赛",
    1023: "匈丙(东南)",
    1025: "俄乙A金组",
    1028: "中北美中美洲杯",
    1026: "俄乙A银组",
    1030: "戈亚斯乙",
    1031: "不丹超",
    1035: "里约杯",
    1041: "葡U19",
    1065: "乌克兰U19联赛",
    1067: "阿根廷业余杯",
    1075: "乌兹甲A",
    1076: "卡德里U20",
    1086: "圣保罗U20",
    1087: "芬K2",
    1090: "北新南威尔士联1",
    1091: "塔斯马尼亚北冠",
    1093: "塔斯马尼亚南冠",
    1094: "西澳州联1",
    1098: "圣保罗B",
    1100: "巴西U20",
    1103: "北爱女超",
    1106: "卡里奥卡C",
    1107: "米内罗U20",
    1112: "塞阿拉U20",
    1113: "委内瑞拉杯",
    1126: "爱沙丙",
    1127: "查塔姆杯",
    1128: "巴U17",
    1138: "帕拉三",
    1147: "卡皮沙B",
    1148: "马拉二",
    1158: "高卓杯",
    1182: "加女超",
    1189: "东南亚女足锦标赛",
    1200: "墨U21联",
    1226: "维多利亚超级2",
    1229: "秘鲁女联",
    1230: "新南威尔士U20",
    1231: "尼日利亚杯",
    1232: "秘鲁联赛杯",
    1234: "韩K4",
    1237: "中美洲及加勒比运动会",
    1239: "奥地区北",
}

# Country label for generic ``{country}超`` fallback.
_COUNTRY_ZH: dict[str, str] = {
    "England": "英格兰",
    "Malta": "马耳他",
    "Israel": "以色列",
    "Wales": "威尔士",
    "Uganda": "乌干达",
    "Bahrain": "巴林",
    "Bangladesh": "孟加拉",
    "Ghana": "加纳",
    "Libya": "利比亚",
    "Kuwait": "科威特",
    "Hong-Kong": "香港",
    "Hong Kong": "香港",
    "Singapore": "新加坡",
    "Jamaica": "牙买加",
    "India": "印度",
    "Lithuania": "立陶宛",
    "Ireland": "爱尔兰",
    "Scotland": "苏格兰",
    "Northern-Ireland": "北爱尔兰",
    "Northern Ireland": "北爱尔兰",
}


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _norm_country(country: str | None) -> str:
    return (country or "").strip()


def _country_key(country: str) -> str:
    return country.strip().replace(" ", "-")


def _country_matches(country: str, allowed: list[str]) -> bool:
    normalized = _country_key(country)
    for entry in allowed:
        candidate = _country_key(entry)
        if candidate == normalized:
            return True
        if candidate.replace("-", " ") == normalized.replace("-", " "):
            return True
    return False


def _lookup_name_country(name: str, country: str) -> str | None:
    if not country:
        return None
    return _BY_NAME_COUNTRY.get(f"{name}|{country}") or _BY_NAME_COUNTRY.get(
        f"{name}|{_country_key(country)}"
    )


def _catalog_name(settings: Settings, league_id: int, fallback: str = "") -> str:
    return settings.league_display_names.get(league_id) or fallback


def _id_countries(settings: Settings, league_id: int) -> list[str]:
    if league_id in settings.LEAGUE_COUNTRIES:
        return [settings.LEAGUE_COUNTRIES[league_id]]
    return []


def _generic_country_label(country: str) -> str | None:
    if not country:
        return None
    return (
        _COUNTRY_ZH.get(country)
        or _COUNTRY_ZH.get(_country_key(country))
        or _COUNTRY_ZH.get(country.replace("-", " "))
    )


def _generic_league_name(name: str, country: str) -> str | None:
    label = _generic_country_label(country)
    if not label:
        return None
    if name in {"Premier League", "Super League"}:
        return f"{label}超"
    if name == "Pro League":
        return f"{label}联赛"
    if name in {"First Division", "Second Division"}:
        tier = "甲" if name == "First Division" else "乙"
        return f"{label}{tier}"
    return None


def league_name_zh(
    name: str | None,
    *,
    league_id: int | None = None,
    country: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Resolve a display name; prefer configured/reference 中文, then name+country rules."""
    cfg = settings or get_settings()
    country_n = _norm_country(country)

    if league_id is not None:
        catalog = _catalog_name(cfg, league_id, "")
        if catalog and _has_cjk(catalog):
            allowed = _id_countries(cfg, league_id)
            if not allowed or not country_n or _country_matches(country_n, allowed):
                return catalog
        by_id = _BY_ID.get(league_id)
        if by_id:
            return by_id

    if not name or not str(name).strip():
        if league_id is not None:
            return _catalog_name(cfg, league_id, "") or f"League {league_id}"
        return ""

    trimmed = str(name).strip()
    if _has_cjk(trimmed):
        return trimmed

    by_country = _lookup_name_country(trimmed, country_n)
    if by_country:
        return by_country

    if league_id is not None:
        catalog = _catalog_name(cfg, league_id, trimmed)
        if catalog and _has_cjk(catalog):
            allowed = _id_countries(cfg, league_id)
            if not allowed or not country_n or _country_matches(country_n, allowed):
                if not (
                    trimmed in _COUNTRY_SCOPED_NAMES
                    and allowed
                    and country_n
                    and not _country_matches(country_n, allowed)
                ):
                    return catalog

    # Pure-name translation is reserved for globally unambiguous competition
    # names. Country-scoped names must never fall through to a popular league.
    if trimmed in _BY_UNAMBIGUOUS_NAME:
        return _BY_UNAMBIGUOUS_NAME[trimmed]

    if trimmed in _COUNTRY_SCOPED_NAMES and country_n:
        generic = _generic_league_name(trimmed, country_n)
        if generic:
            return generic

    if "Friendly" in trimmed:
        return "俱乐部友谊赛" if "Club" in trimmed else "友谊赛"

    return trimmed


async def backfill_league_names(session) -> int:
    """Rewrite non-catalog ``leagues.name`` from the built-in id/name map.

    Catalog rows stay under admin-maintained ``leagues.name``.
    """
    from sqlalchemy import select

    from app.models.league import League

    rows = (await session.execute(select(League))).scalars().all()
    updated = 0
    for row in rows:
        if row.is_catalog:
            continue
        zh = league_name_zh(row.name, league_id=row.id, country=row.country)
        if zh and zh != row.name:
            row.name = zh
            updated += 1
    await session.commit()
    return updated


def localize_match_row(match: dict[str, Any]) -> dict[str, Any]:
    """Localize team + league labels on a form/H2H row."""
    from app.services.team_names import localize_match_teams

    row = localize_match_teams(dict(match))
    league_id_raw = row.get("league_id")
    try:
        league_id = int(league_id_raw) if league_id_raw is not None else None
    except (TypeError, ValueError):
        league_id = None
    country_raw = row.get("league_country")
    country = str(country_raw).strip() if country_raw else None
    raw_name = row.get("league_name")
    row["league_name"] = league_name_zh(
        raw_name if isinstance(raw_name, str) else None,
        league_id=league_id,
        country=country,
    )
    return row


def localize_matches_block(block: dict[str, Any] | None) -> dict[str, Any]:
    """Localize all match rows inside a form / H2H summary dict."""
    if not isinstance(block, dict):
        return {"played": 0, "matches": []}
    matches = block.get("matches")
    if isinstance(matches, list):
        block = {
            **block,
            "matches": [
                localize_match_row(dict(m)) for m in matches if isinstance(m, dict)
            ],
        }
    return block
