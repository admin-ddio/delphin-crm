/** ISO 3166-1 alpha-2 countries with English names (Intl) and flag emoji. */

const CODES =
  'AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split(
    ' ',
  );

/** Shown first in pickers (the agency's usual markets). */
const COMMON = ['IN', 'US', 'GB', 'AE', 'SG', 'AU', 'CA'];

const names = new Intl.DisplayNames(['en'], { type: 'region' });

export function countryName(code: string | null | undefined): string {
  if (!code) return '—';
  try {
    return names.of(code) ?? code;
  } catch {
    return code;
  }
}

export function flag(code: string | null | undefined): string {
  if (!code || code.length !== 2) return '';
  return String.fromCodePoint(
    ...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65),
  );
}

export const COUNTRY_OPTIONS: { value: string; label: string }[] = [
  ...COMMON,
  ...CODES.filter((c) => !COMMON.includes(c)).sort((a, b) =>
    countryName(a).localeCompare(countryName(b)),
  ),
].map((code) => ({ value: code, label: countryName(code) }));

/** Dial codes for the phone pickers (common markets; others type it in). */
export const DIAL_CODES = ['+91', '+1', '+44', '+971', '+65', '+61', '+49', '+33', '+81'];
