/**
 * Common competition display names (API-Sports English → 中文).
 * Unmapped names are returned as-is.
 */
const BY_NAME: Record<string, string> = {
  'Premier League': '英超',
  Championship: '英冠',
  'League One': '英甲',
  'League Two': '英乙',
  'FA Cup': '足总杯',
  'EFL Cup': '联赛杯',
  'La Liga': '西甲',
  'Segunda División': '西乙',
  'Copa Del Rey': '国王杯',
  'Serie A': '意甲',
  'Serie B': '意乙',
  'Coppa Italia': '意大利杯',
  Bundesliga: '德甲',
  '2. Bundesliga': '德乙',
  'DFB Pokal': '德国杯',
  'Ligue 1': '法甲',
  'Ligue 2': '法乙',
  'Coupe de France': '法国杯',
  Eredivisie: '荷甲',
  'Primeira Liga': '葡超',
  'UEFA Champions League': '欧冠',
  'UEFA Europa League': '欧联',
  'UEFA Europa Conference League': '欧协联',
  'UEFA Super Cup': '欧洲超级杯',
  'World Cup': '世界杯',
  'Euro Championship': '欧洲杯',
  'Africa Cup of Nations': '非洲杯',
  'Copa America': '美洲杯',
  'Confederations Cup': '联合会杯',
  Friendlies: '友谊赛',
  'World Cup - Qualification Europe': '世预赛(欧)',
  'World Cup - Qualification Africa': '世预赛(非)',
  'World Cup - Qualification South America': '世预赛(南美)',
  'World Cup - Qualification Asia': '世预赛(亚)',
  'UEFA Nations League': '欧国联',
  'Scottish Premiership': '苏超',
  'Pro League': '比甲',
  'Super Lig': '土超',
  'Saudi Pro League': '沙特联',
  'Major League Soccer': '美职联',
  'A-League': '澳超',
  'J1 League': '日职联',
  'K League 1': '韩K联',
  'Chinese Super League': '中超',
}

export function leagueNameZh(name?: string | null): string {
  if (!name) return ''
  return BY_NAME[name] ?? name
}
