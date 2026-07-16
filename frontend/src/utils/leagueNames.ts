/**
 * Competition display names (API-Sports English → 中文).
 * Prefer backend/catalog 中文名，再 league_id，再 name+country，最后 bare name。
 */

/** Stable API-Sports league ids → 中文 */
const BY_ID: Record<number, string> = {
  1: '世界杯',
  2: '欧冠',
  3: '欧罗巴',
  4: '欧洲杯',
  5: '欧国联',
  9: '美洲杯',
  10: '亚冠',
  15: '联合会杯',
  17: '亚冠精英',
  39: '英超',
  40: '英冠',
  41: '英甲',
  42: '英乙',
  45: '足总杯',
  48: '联赛杯',
  61: '法甲',
  62: '法乙',
  66: '法国杯',
  71: '巴甲',
  78: '德甲',
  79: '德乙',
  81: '德国杯',
  88: '荷甲',
  94: '葡超',
  98: '日职联',
  135: '意甲',
  136: '意乙',
  137: '意大利杯',
  140: '西甲',
  141: '西乙',
  143: '国王杯',
  144: '比甲',
  169: '中超',
  170: '中甲',
  171: '足协杯',
  203: '土超',
  242: '厄甲',
  253: '美职联',
  292: '韩K联',
  294: '韩国杯',
  307: '沙特联',
  344: '玻利甲',
  369: '乌兹超',
  848: '欧协联',
}

/** Bare English name → 中文（无歧义或默认指欧洲主流） */
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
  'UEFA Europa League': '欧罗巴',
  'UEFA Europa Conference League': '欧协联',
  'UEFA Super Cup': '欧洲超级杯',
  'AFC Champions League': '亚冠',
  'AFC Champions League Elite': '亚冠精英',
  'AFC Champions League Two': '亚冠二级',
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
  'Liga Pro': '厄甲',
  'Super Lig': '土超',
  'Saudi Pro League': '沙特联',
  'Major League Soccer': '美职联',
  MLS: '美职联',
  'Brazil Serie A': '巴甲',
  'Serie A - Brazil': '巴甲',
  'A-League': '澳超',
  'J1 League': '日职联',
  'K League 1': '韩K联',
  'Korea Cup': '韩国杯',
  'Chinese Super League': '中超',
  'China League One': '中甲',
  'China League Two': '中乙',
  CFA: '足协杯',
  'Chinese FA Cup': '足协杯',
}

/**
 * Ambiguous English names disambiguated by country.
 * Key: `${name}|${country}` (country as returned by API-Sports).
 */
const BY_NAME_COUNTRY: Record<string, string> = {
  'League One|China': '中甲',
  'League Two|China': '中乙',
  'Super League|China': '中超',
  'Super League|Uzbekistan': '乌兹超',
  'Super League|Switzerland': '瑞士超',
  'FA Cup|China': '足协杯',
  'FA Cup|England': '足总杯',
  'FA Cup|South-Korea': '韩国杯',
  'FA Cup|South Korea': '韩国杯',
  'Korea Cup|South-Korea': '韩国杯',
  'Korea Cup|South Korea': '韩国杯',
  'Serie A|Brazil': '巴甲',
  'Serie A|Italy': '意甲',
  'Serie B|Italy': '意乙',
  'League One|England': '英甲',
  'League Two|England': '英乙',
  'Pro League|Belgium': '比甲',
  'Pro League|Saudi-Arabia': '沙特联',
  'Pro League|Saudi Arabia': '沙特联',
  'Liga Pro|Ecuador': '厄甲',
  'Primera División|Bolivia': '玻利甲',
  'Division Profesional|Bolivia': '玻利甲',
}

function normCountry(country?: string | null): string {
  return (country || '').trim()
}

export function leagueNameZh(
  name?: string | null,
  opts?: { leagueId?: number | null; country?: string | null },
): string {
  if (!name) {
    if (opts?.leagueId != null && BY_ID[opts.leagueId]) {
      return BY_ID[opts.leagueId]
    }
    return ''
  }
  const trimmed = name.trim()
  if (/[\u4e00-\u9fff]/.test(trimmed)) return trimmed
  if (opts?.leagueId != null && BY_ID[opts.leagueId]) {
    return BY_ID[opts.leagueId]
  }
  const country = normCountry(opts?.country)
  if (country) {
    const keyed = BY_NAME_COUNTRY[`${trimmed}|${country}`]
    if (keyed) return keyed
  }
  return BY_NAME[trimmed] ?? trimmed
}
