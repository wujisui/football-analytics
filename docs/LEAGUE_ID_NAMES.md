# 联赛名称与官方 ID

本表是本机数据库 `leagues` 的查阅副本，**不是运行时真源**。
目录中文名以管理员维护的 `leagues.name` 为准；目录外展示名以 `league_names.py` 为准（按官方 ID，同名再加国家）。
管理员在「热门联赛」改完目录后，需要时再重刷本文件。

- 快照日期：2026-08-27
- 库路径：`backend/data/football.db`
- 合计 308 条：目录 42，目录外 266
- 官方 ID 即 API-Sports `league.id`
- 系统保护（不可删、不可改官方 ID）：英超 39、西甲 140、德甲 78、意甲 135、法甲 61、荷甲 88、葡超 94、欧冠 2、中超 169

## 目录联赛

出现在热门联赛配置页。同一英文名可能对应不同国家，以官方 ID 为准。

### 五大联赛

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 39 | 英超 | England | 是 | 是 |
| 61 | 法甲 | France | 是 | 是 |
| 78 | 德甲 | Germany | 是 | 是 |
| 135 | 意甲 | Italy | 是 | 是 |
| 140 | 西甲 | Spain | 是 | 是 |

### 欧洲杯赛

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 2 | 欧冠 | World | 是 | 是 |
| 3 | 欧罗巴 | World | 是 |  |
| 848 | 欧协联 | World | 是 |  |

### 其他欧洲

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 40 | 英冠 | England | 是 |  |
| 62 | 法乙 | France | 是 |  |
| 79 | 德乙 | Germany | 是 |  |
| 88 | 荷甲 | Netherlands | 是 | 是 |
| 89 | 荷乙 | Netherlands | 是 |  |
| 94 | 葡超 | Portugal | 是 | 是 |
| 103 | 挪超 | Norway | 是 |  |
| 113 | 瑞典超 | Sweden |  |  |
| 179 | 苏超 | Scotland |  |  |

### 国际赛事

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 1 | 世界杯 | World |  |  |
| 5 | 欧国联 | World |  |  |
| 22 | 金杯赛 | World |  |  |

### 洲际杯赛

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 4 | 欧洲杯 | World |  |  |
| 6 | 非洲杯 | World |  |  |
| 7 | 亚洲杯 | World |  |  |
| 9 | 美洲杯 | World |  |  |
| 11 | 南美杯 | World | 是 |  |
| 13 | 解放者杯 | World | 是 |  |
| 16 | 世俱杯 | World |  |  |

### 美洲

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 71 | 巴甲 | Brazil | 是 |  |
| 128 | 阿甲 | Argentina | 是 |  |
| 253 | 美职联 | USA | 是 |  |

### 亚洲及大洋洲

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 17 | 亚冠精英 | World |  |  |
| 98 | 日职联 | Japan | 是 |  |
| 169 | 中超 | China | 是 | 是 |
| 188 | 澳超 | Australia |  |  |
| 292 | 韩K联 | South-Korea | 是 |  |
| 307 | 沙特联 | Saudi-Arabia | 是 |  |

### 杯赛

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 48 | 英联杯 | England | 是 |  |
| 81 | 德国杯 | Germany |  |  |
| 102 | 日皇杯 | Japan | 是 |  |
| 528 | 社区盾杯 | England |  |  |

### 友谊赛

| 官方 ID | 名称 | 国家 | 热门 | 保护 |
| ---: | --- | --- | :---: | :---: |
| 10 | 国际友谊赛 | World |  |  |
| 667 | 俱乐部友谊赛 | World |  |  |

## 目录外联赛

赛程入库带进来的行，不在热门联赛勾选目录里；筛选框里可能进「其他」。
下表名称已按 `league_names.py` 译成中文。同名赛事必须看 ID + 国家。

| 官方 ID | 名称 | 国家 |
| ---: | --- | --- |
| 24 | 东南亚锦标赛 | World |
| 43 | 英全国联 | England |
| 50 | 英全国联北 | England |
| 51 | 英全国联南 | England |
| 58 | 英依斯米安超 | England |
| 59 | 英北部超 | England |
| 60 | 英南部超(南) | England |
| 63 | 法丙 | France |
| 72 | 巴乙 | Brazil |
| 73 | 巴西杯 | Brazil |
| 74 | 巴女甲 | Brazil |
| 75 | 巴丙 | Brazil |
| 76 | 巴丁 | Brazil |
| 80 | 德丙 | Germany |
| 84 | 德地区北 | Germany |
| 85 | 德地区东北 | Germany |
| 86 | 德地区西南 | Germany |
| 87 | 德地区西 | Germany |
| 95 | 葡甲 | Portugal |
| 100 | 日丙 | Japan |
| 104 | 挪甲 | Norway |
| 106 | 波超 | Poland |
| 107 | 波乙 | Poland |
| 108 | 波兰杯 | Poland |
| 109 | 波丙(东) | Poland |
| 110 | 威超 | Wales |
| 111 | 威甲 | Wales |
| 114 | 瑞典甲 | Sweden |
| 115 | 瑞典杯 | Sweden |
| 116 | 白俄超 | Belarus |
| 117 | 白俄甲 | Belarus |
| 119 | 丹超 | Denmark |
| 120 | 丹甲 | Denmark |
| 121 | 丹麦杯 | Denmark |
| 122 | 丹乙 | Denmark |
| 129 | 阿乙 | Argentina |
| 130 | 阿根廷杯 | Argentina |
| 131 | 阿丙(大都会) | Argentina |
| 132 | 阿丁 | Argentina |
| 134 | 阿根廷联邦A | Argentina |
| 137 | 意大利杯 | Italy |
| 144 | 比甲 | Belgium |
| 162 | 哥斯达黎加甲 | Costa-Rica |
| 163 | 哥斯达黎加乙 | Costa-Rica |
| 164 | 冰岛超 | Iceland |
| 165 | 冰岛甲 | Iceland |
| 166 | 冰岛乙 | Iceland |
| 167 | 冰岛杯 | Iceland |
| 170 | 中甲 | China |
| 171 | 中协杯 | China |
| 172 | 保超 | Bulgaria |
| 173 | 保乙 | Bulgaria |
| 180 | 苏冠 | Scotland |
| 183 | 苏甲 | Scotland |
| 184 | 苏乙 | Scotland |
| 185 | 苏格兰联赛杯 | Scotland |
| 189 | 澳首都NPL | Australia |
| 192 | 新南威尔士NPL | Australia |
| 194 | 南澳NPL | Australia |
| 195 | 维多利亚NPL | Australia |
| 196 | 西澳NPL | Australia |
| 199 | 希腊杯 | Greece |
| 200 | 摩洛哥超 | Morocco |
| 203 | 土超 | Turkey |
| 204 | 土甲 | Turkey |
| 207 | 瑞士超 | Switzerland |
| 208 | 瑞士挑战联 | Switzerland |
| 210 | 克罗地亚甲 | Croatia |
| 218 | 奥超 | Austria |
| 219 | 奥乙 | Austria |
| 220 | 奥地利杯 | Austria |
| 221 | 奥地区东 | Austria |
| 234 | 洪都拉斯甲 | Honduras |
| 235 | 俄超 | Russia |
| 236 | 俄甲 | Russia |
| 237 | 俄罗斯杯 | Russia |
| 238 | 俄青联 | Russia |
| 239 | 哥伦甲 | Colombia |
| 240 | 哥伦乙 | Colombia |
| 241 | 哥伦杯 | Colombia |
| 242 | 厄甲 | Ecuador |
| 243 | 厄乙 | Ecuador |
| 244 | 芬超 | Finland |
| 245 | 芬甲 | Finland |
| 247 | 芬丙A组 | Finland |
| 248 | 芬丙B组 | Finland |
| 249 | 芬丙C组 | Finland |
| 251 | 巴拉乙 | Paraguay |
| 252 | 巴拉甲 | Paraguay |
| 254 | 美女职 | USA |
| 255 | 美冠联 | USA |
| 261 | 卢森堡甲 | Luxembourg |
| 262 | 墨超 | Mexico |
| 263 | 墨扩军联 | Mexico |
| 265 | 智利甲 | Chile |
| 266 | 智利乙 | Chile |
| 267 | 智利杯 | Chile |
| 268 | 乌拉甲 | Uruguay |
| 269 | 乌拉乙 | Uruguay |
| 271 | 匈甲 | Hungary |
| 272 | 匈乙 | Hungary |
| 281 | 秘鲁甲 | Peru |
| 282 | 秘鲁乙 | Peru |
| 283 | 罗甲 | Romania |
| 284 | 罗乙 | Romania |
| 285 | 罗马尼亚杯 | Romania |
| 286 | 塞超 | Serbia |
| 287 | 塞甲 | Serbia |
| 288 | 南非超 | South-Africa |
| 290 | 伊朗超 | Iran |
| 293 | 韩K2 | South-Korea |
| 294 | 韩国杯 | South-Korea |
| 295 | 韩K3 | South-Korea |
| 299 | 委内甲 | Venezuela |
| 300 | 委内乙 | Venezuela |
| 304 | 巴拿马甲 | Panama |
| 305 | 卡塔尔星联 | Qatar |
| 315 | 波黑超 | Bosnia |
| 326 | 格鲁吉亚甲 | Georgia |
| 327 | 格鲁吉亚超 | Georgia |
| 328 | 爱沙乙 | Estonia |
| 329 | 爱沙超 | Estonia |
| 331 | 科威特甲 | Kuwait |
| 332 | 斯洛伐克超 | Slovakia |
| 333 | 乌克超 | Ukraine |
| 334 | 乌克乙 | Ukraine |
| 339 | 危地马拉甲 | Guatemala |
| 342 | 亚美尼亚超 | Armenia |
| 344 | 玻利甲 | Bolivia |
| 345 | 捷甲 | Czech-Republic |
| 346 | 捷乙 | Czech-Republic |
| 347 | 捷克杯 | Czech-Republic |
| 348 | 捷丙CFL A | Czech-Republic |
| 349 | 捷丙MSFL | Czech-Republic |
| 350 | 捷丁A | Czech-Republic |
| 352 | 捷丁C | Czech-Republic |
| 353 | 捷丁D | Czech-Republic |
| 354 | 捷丁E | Czech-Republic |
| 355 | 黑山超 | Montenegro |
| 357 | 爱超 | Ireland |
| 358 | 爱甲 | Ireland |
| 361 | 立甲 | Lithuania |
| 362 | 立乙 | Lithuania |
| 364 | 拉脱甲 | Latvia |
| 365 | 拉脱超 | Latvia |
| 366 | 法罗甲 | Faroe-Islands |
| 367 | 法罗超 | Faroe-Islands |
| 369 | 乌兹超 | Uzbekistan |
| 370 | 萨尔瓦多甲 | El-Salvador |
| 371 | 北马其甲 | Macedonia |
| 373 | 斯洛文甲 | Slovenia |
| 374 | 斯洛文乙 | Slovenia |
| 385 | 以色列图图杯 | Israel |
| 388 | 哈萨克甲 | Kazakhstan |
| 389 | 哈萨克超 | Kazakhstan |
| 390 | 黎巴嫩超 | Lebanon |
| 391 | 马拉维超 | Malawi |
| 394 | 摩尔多瓦超 | Moldova |
| 396 | 尼加拉瓜甲 | Nicaragua |
| 401 | 津巴布韦超 | Zimbabwe |
| 407 | 北爱冠 | Northern-Ireland |
| 408 | 北爱超 | Northern-Ireland |
| 473 | 挪丙1组 | Norway |
| 474 | 挪丙2组 | Norway |
| 479 | 加超 | Canada |
| 481 | 北新南威尔士NPL | Australia |
| 482 | 昆士兰NPL | Australia |
| 484 | 奥女甲 | Austria |
| 489 | 美职联三级 | USA |
| 501 | 巴拉圭杯 | Paraguay |
| 506 | 斯洛伐克乙 | Slovakia |
| 509 | 南非8强杯 | South-Africa |
| 510 | 瑞士晋级联 | Switzerland |
| 525 | 女足欧冠 | World |
| 537 | 中北美U20 | World |
| 549 | 瑞典女超 | Sweden |
| 563 | 瑞典乙北 | Sweden |
| 564 | 瑞典乙南 | Sweden |
| 566 | 布隆迪甲 | Burundi |
| 567 | 坦桑尼亚超 | Tanzania |
| 569 | 吉尔吉斯超 | Kyrgyzstan |
| 592 | 瑞典丙西约塔北 | Sweden |
| 593 | 瑞典丙斯维兰北 | Sweden |
| 594 | 瑞典丙诺尔兰 | Sweden |
| 595 | 瑞典丙斯维兰南 | Sweden |
| 596 | 瑞典丙西约塔西 | Sweden |
| 597 | 瑞典丙南约塔 | Sweden |
| 619 | 米内罗二 | Brazil |
| 633 | 匈丙(东北) | Hungary |
| 635 | 匈丙(西北) | Hungary |
| 645 | 斯洛伐克丙(东) | Slovakia |
| 648 | 塔斯马尼亚NPL | Australia |
| 650 | 俄乙3组 | Russia |
| 651 | 俄乙1组 | Russia |
| 653 | 俄乙4组 | Russia |
| 657 | 爱沙杯 | Estonia |
| 660 | 韩女联 | South-Korea |
| 668 | 捷U19甲 | Czech-Republic |
| 673 | 墨超女足 | Mexico |
| 680 | 斯洛伐克杯 | Slovakia |
| 685 | 捷丙CFL B | Czech-Republic |
| 711 | 智利乙 | Chile |
| 712 | 哥伦女甲 | Colombia |
| 730 | 苏高地联 | Scotland |
| 731 | 苏低地联 | Scotland |
| 736 | 瑞典女甲 | Sweden |
| 740 | 巴U20A | Brazil |
| 742 | 圣保罗杯 | Brazil |
| 772 | 美墨联赛杯 | World |
| 774 | 挪丁1组 | Norway |
| 775 | 挪丁2组 | Norway |
| 776 | 挪丁3组 | Norway |
| 777 | 挪丁4组 | Norway |
| 778 | 挪丁5组 | Norway |
| 779 | 挪丁6组 | Norway |
| 780 | 波丁1组 | Poland |
| 781 | 波丁2组 | Poland |
| 782 | 波丁3组 | Poland |
| 783 | 波丁4组 | Poland |
| 823 | 挪U19冠军杯 | Norway |
| 833 | 昆士兰超级联 | Australia |
| 834 | 南澳州联1 | Australia |
| 835 | 新南威尔士NPL2 | Australia |
| 836 | 维多利亚NPL2 | Australia |
| 856 | 中北美加勒比俱乐部锦标赛 | World |
| 862 | 丹丙 | Denmark |
| 865 | 葡丙 | Portugal |
| 869 | 东非俱乐部杯 | World |
| 874 | 澳大利亚杯 | Australia |
| 906 | 阿预备联 | Argentina |
| 909 | 美职预备联 | USA |
| 917 | 厄瓜多尔杯 | Ecuador |
| 924 | 印尼总统杯 | Indonesia |
| 929 | 中乙 | China |
| 931 | 英南部超(中) | England |
| 936 | 卡德里二 | Brazil |
| 1016 | 中美洲及加勒比运动会 | World |
| 1020 | 加尔各答超 | India |
| 1023 | 匈丙(东南) | Hungary |
| 1025 | 俄乙A金组 | Russia |
| 1026 | 俄乙A银组 | Russia |
| 1028 | 中北美中美洲杯 | World |
| 1030 | 戈亚斯乙 | Brazil |
| 1031 | 不丹超 | Bhutan |
| 1035 | 里约杯 | Brazil |
| 1041 | 葡U19 | Portugal |
| 1067 | 阿根廷业余杯 | Argentina |
| 1075 | 乌兹甲A | Uzbekistan |
| 1086 | 圣保罗U20 | Brazil |
| 1087 | 芬K2 | Finland |
| 1093 | 塔斯马尼亚南冠 | Australia |
| 1094 | 西澳州联1 | Australia |
| 1106 | 卡里奥卡C | Brazil |
| 1107 | 米内罗U20 | Brazil |
| 1112 | 塞阿拉U20 | Brazil |
| 1113 | 委内瑞拉杯 | Venezuela |
| 1126 | 爱沙丙 | Estonia |
| 1148 | 马拉二 | Brazil |
| 1158 | 高卓杯 | Brazil |
| 1200 | 墨U21联 | Mexico |
| 1226 | 维多利亚超级2 | Australia |
| 1229 | 秘鲁女联 | Peru |
| 1230 | 新南威尔士U20 | Australia |
| 1234 | 韩K4 | South-Korea |
| 1237 | 中美洲及加勒比运动会 | World |
| 1239 | 奥地区北 | Austria |
