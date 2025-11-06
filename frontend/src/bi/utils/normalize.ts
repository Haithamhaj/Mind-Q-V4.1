'use client';

const ARABIC_CHAR_REGEX = /[\u0600-\u06FF]/;
const ALPHANUMERIC_REGEX = /^[a-z0-9/]+$/i;

const VALUE_ALIASES: Record<string, string> = {
  cc: "CC",
  cod: "COD",
  "cash on delivery": "Cash On Delivery",
  "cash collected (cod)": "Cash Collected (COD)",
  "cash_on_delivery": "Cash On Delivery",
  "credit card": "Credit Card",
  "credit-card": "Credit Card",
  "credit_card": "Credit Card",
  "creditcard": "Credit Card",
  riyadh: "الرياض",
  "riyadh city": "الرياض",
  "al riyadh": "الرياض",
  "ar riyadh": "الرياض",
  "riyadh province": "الرياض",
  makkah: "مكة المكرمة",
  "makkah province": "مكة المكرمة",
  "mecca": "مكة المكرمة",
  medina: "المدينة المنورة",
  madinah: "المدينة المنورة",
  "al madinah": "المدينة المنورة",
  jeddah: "جدة",
  "jeddah city": "جدة",
  dammam: "الدمام",
  "al dammam": "الدمام",
  tabuk: "تبوك",
  abha: "أبها",
  "al khobar": "الخبر",
  khobar: "الخبر",
  qassim: "القصيم",
  hail: "حائل",
  taif: "الطائف",
  "al taif": "الطائف",
  smsa: "سمسا",
  "smsa express": "سمسا",
  "smsa_express": "سمسا",
  "سمسا": "سمسا",
  spl: "SPL",
  "spl company": "SPL",
  "saudi post": "SPL",
  "saudi-post": "SPL",
  "البريد السعودي": "SPL",
  aramex: "أرامكس",
  "aramex express": "أرامكس",
  "aramax": "أرامكس",
  "أرامكس": "أرامكس",
  naqel: "ناقل",
  "naqel express": "ناقل",
  "naqel-express": "ناقل",
  "naqel logistics": "ناقل",
  "naql": "ناقل",
  "ناقل": "ناقل",
  "j&t": "J&T Express",
  "j&t express": "J&T Express",
  "jt express": "J&T Express",
  "j and t": "J&T Express",
  "جي اند تي": "J&T Express",
  "zajil": "زاجل",
  "زاجل": "زاجل",
  barq: "Barq",
  "بارق": "بارق",
  fetchr: "Fetchr",
  dhl: "DHL",
  "dhl express": "DHL",
  ups: "UPS",
  fedex: "FedEx",
  tnt: "TNT",
};

const CANONICAL_DIMENSION_ALIASES: Record<string, Record<string, string>> = {
  payment_method: {
    cc: "CC",
    "credit card": "CC",
    "credit_card": "CC",
    "credit-card": "CC",
    "creditcard": "CC",
    cod: "COD",
    "cash on delivery": "COD",
    "cash-on-delivery": "COD",
    "cash_on_delivery": "COD",
    "receiver_cod": "COD",
  },
  destination: {
    riyadh: "الرياض",
    "riyadh city": "الرياض",
    "al riyadh": "الرياض",
    "ar riyadh": "الرياض",
    "riyadh province": "الرياض",
    "الرياض": "الرياض",
    makkah: "مكة المكرمة",
    "makkah province": "مكة المكرمة",
    "mecca": "مكة المكرمة",
    "مكة": "مكة المكرمة",
    "مكة المكرمة": "مكة المكرمة",
    jeddah: "جدة",
    "جدة": "جدة",
    dammam: "الدمام",
    "الدمام": "الدمام",
    tabuk: "تبوك",
    "تبوك": "تبوك",
    abha: "أبها",
    "أبها": "أبها",
    taif: "الطائف",
    "al taif": "الطائف",
    "الطائف": "الطائف",
    hail: "حائل",
    "حائل": "حائل",
    khobar: "الخبر",
    "al khobar": "الخبر",
    "الخبر": "الخبر",
    qassim: "القصيم",
    "al qassim": "القصيم",
    "القصيم": "القصيم",
    medina: "المدينة المنورة",
    madinah: "المدينة المنورة",
    "al madinah": "المدينة المنورة",
    "المدينة": "المدينة المنورة",
    "المدينة المنورة": "المدينة المنورة",
  },
};

const LOGISTICS_DIMENSION_KEYS = [
  "carrier",
  "carrier_name",
  "courier",
  "courier_name",
  "delivery_company",
  "delivery_partner",
  "delivery_provider",
  "delivery_service",
  "fulfillment_partner",
  "fulfillment_provider",
  "last_mile_carrier",
  "lastmile_carrier",
  "logistics_company",
  "logistics_partner",
  "logistics_provider",
  "shipping_company",
  "shipment_carrier",
  "vendor",
  "service_provider",
];

const LOGISTICS_ALIASES: Record<string, string> = {
  smsa: "سمسا",
  "smsa express": "سمسا",
  "smsa_express": "سمسا",
  "سمسا": "سمسا",
  aramex: "أرامكس",
  "aramex express": "أرامكس",
  "aramax": "أرامكس",
  "أرامكس": "أرامكس",
  naqel: "ناقل",
  "naqel express": "ناقل",
  "naqel-express": "ناقل",
  "naqel logistics": "ناقل",
  "naql": "ناقل",
  "ناقل": "ناقل",
  "j&t": "J&T Express",
  "j&t express": "J&T Express",
  "jt express": "J&T Express",
  "j and t": "J&T Express",
  "جي اند تي": "J&T Express",
  spl: "SPL",
  "spl company": "SPL",
  "saudi post": "SPL",
  "saudi-post": "SPL",
  "البريد السعودي": "SPL",
  "مؤسسة البريد السعودي": "SPL",
  zajil: "زاجل",
  "زاجل": "زاجل",
  barq: "Barq",
  "بارق": "بارق",
  fetchr: "Fetchr",
  dhl: "DHL",
  "dhl express": "DHL",
  ups: "UPS",
  fedex: "FedEx",
  tnt: "TNT",
  "smsa logistics": "سمسا",
};

for (const key of LOGISTICS_DIMENSION_KEYS) {
  CANONICAL_DIMENSION_ALIASES[key] = {
    ...(CANONICAL_DIMENSION_ALIASES[key] ?? {}),
    ...LOGISTICS_ALIASES,
  };
}

const normalizeDimensionKey = (rawKey: string): string => {
  const normalized = rawKey.trim().toLowerCase();
  if (!normalized) {
    return normalized;
  }
  if (normalized in CANONICAL_DIMENSION_ALIASES) {
    return normalized;
  }
  if (
    normalized.includes("payment") ||
    normalized.includes("pay_method") ||
    normalized.includes("paymethod") ||
    normalized.includes("receiver_mode") ||
    normalized.includes("receiver-mode")
  ) {
    return "payment_method";
  }
  if (
    normalized.includes("destination") ||
    normalized.includes("dest_city") ||
    normalized.includes("city") ||
    normalized.includes("region")
  ) {
    return "destination";
  }
  if (
    normalized.includes("carrier") ||
    normalized.includes("courier") ||
    normalized.includes("delivery_company") ||
    normalized.includes("delivery-company") ||
    normalized.includes("delivery_provider") ||
    normalized.includes("logistics") ||
    normalized.includes("shipping")
  ) {
    return "carrier";
  }
  return normalized;
};

const titleCase = (value: string) =>
  value
    .toLowerCase()
    .split(/\s+/g)
    .filter((token) => token.length > 0)
    .map((token) => {
      const alphaLength = token.replace(/[^a-z]/g, "").length;
      if (alphaLength > 0 && alphaLength <= 4 && /^[a-z0-9&+/.-]+$/.test(token)) {
        return token.replace(/[a-z]/g, (char) => char.toUpperCase());
      }
      return token.charAt(0).toUpperCase() + token.slice(1);
    })
    .join(" ");

const canonicalizePlainValue = (rawValue: string): string => {
  const trimmed = rawValue.replace(/^[\s"'[{(]+|[\s"'[\]})]+$/g, "").replace(/_/g, " ").replace(/\s+/g, " ").trim();
  if (!trimmed) {
    return "";
  }

  const alias = VALUE_ALIASES[trimmed.toLowerCase()];
  if (alias) {
    return alias;
  }

  if (ARABIC_CHAR_REGEX.test(trimmed)) {
    return trimmed;
  }

  if (ALPHANUMERIC_REGEX.test(trimmed) && trimmed.length <= 3) {
    return trimmed.toUpperCase();
  }

  return trimmed.replace(/\b([a-z])([a-z]*)\b/gi, (_, first: string, rest: string) => {
    const token = `${first}${rest}`.toLowerCase();
    if (VALUE_ALIASES[token]) {
      return VALUE_ALIASES[token];
    }
    if (token.length <= 3) {
      return token.toUpperCase();
    }
    return `${first.toUpperCase()}${rest.toLowerCase()}`;
  });
};

export type LabelParts = {
  primary: string;
  secondary?: string;
  combined: string;
};

const parseLocalizationMap = (value: string): Record<string, string> => {
  const mapping: Record<string, string> = {};
  const sanitized = value.trim();
  if (!sanitized) {
    return mapping;
  }

  const normalizedQuotes = sanitized
    .replace(/\\'/g, "__SINGLE_QUOTE__")
    .replace(/'/g, '"')
    .replace(/__SINGLE_QUOTE__/g, "'");
  try {
    const jsonCandidate = normalizedQuotes
      .replace(/\bNone\b/g, "null")
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false");
    const parsed = JSON.parse(jsonCandidate);
    if (parsed && typeof parsed === "object") {
      for (const [rawKey, val] of Object.entries(parsed as Record<string, unknown>)) {
        if (typeof val !== "string") {
          continue;
        }
        const cleanedKey = rawKey.toLowerCase().replace(/^label[_-]?/, "");
        mapping[cleanedKey] = val.trim();
      }
    }
  } catch (error) {
    // Fallback to regex extraction
    const regex = /["']?(en|ar|label[_-]?en|label[_-]?ar|label)["']?\s*[:=]\s*["']([^"'{}]+)["']/gi;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(sanitized))) {
      const lang = match[1].toLowerCase().replace(/^label[_-]?/, "");
      const text = match[2].trim();
      if (text) {
        mapping[lang] = text;
      }
    }
  }

  return mapping;
};

const combineLabel = (primary?: string, secondary?: string): LabelParts => {
  const main = primary?.trim() ?? "";
  const secondaryClean = secondary?.trim();
  if (main && secondaryClean && secondaryClean !== main) {
    return {
      primary: main,
      secondary: secondaryClean,
      combined: `${main} (${secondaryClean})`,
    };
  }
  return {
    primary: main,
    secondary: undefined,
    combined: main,
  };
};

export const resolveLabelParts = (primary?: string | null, fallback?: string | null): LabelParts => {
  const candidate = primary ?? fallback ?? "";
  const trimmed = candidate.trim();
  if (!trimmed) {
    return { primary: "", secondary: undefined, combined: "" };
  }

  const localization = parseLocalizationMap(trimmed);
  const ar = localization.ar?.trim();
  const en = localization.en?.trim() ?? localization.label?.trim();

  const canonicalAr = ar ? canonicalizePlainValue(ar) : undefined;
  const canonicalEn = en ? canonicalizePlainValue(en) : undefined;

  if (canonicalAr && canonicalEn && canonicalAr !== canonicalEn) {
    return combineLabel(canonicalAr, canonicalEn);
  }

  if (canonicalAr) {
    return combineLabel(canonicalAr);
  }

  if (canonicalEn) {
    return combineLabel(canonicalEn);
  }

  const normalized = canonicalizePlainValue(trimmed);
  return combineLabel(normalized);
};

export const canonicalizeDimensionValue = (dimensionKey: string, rawValue: string): string => {
  const collapsed = rawValue.trim();
  if (!collapsed) {
    return "";
  }

  if (collapsed.includes("/")) {
    const parts = collapsed
      .split("/")
      .map((segment) => segment.trim())
      .filter(Boolean)
      .map((segment) => canonicalizeDimensionValue(dimensionKey, segment));
    const uniqueParts = Array.from(new Set(parts.filter(Boolean)));
    if (uniqueParts.length === 1) {
      return uniqueParts[0];
    }
  }

  const effectiveKey = normalizeDimensionKey(dimensionKey);
  const aliasMap = CANONICAL_DIMENSION_ALIASES[effectiveKey];
  const lowerValue = collapsed.toLowerCase();
  const normalizedWhitespace = lowerValue.replace(/[\s/_-]+/g, " ").trim();
  const aliasCandidates = [lowerValue, normalizedWhitespace, collapsed];

  for (const candidate of aliasCandidates) {
    if (aliasMap && aliasMap[candidate]) {
      return aliasMap[candidate];
    }
  }

  for (const candidate of aliasCandidates) {
    const lookupKey = typeof candidate === "string" ? candidate.toLowerCase() : candidate;
    if (VALUE_ALIASES[lookupKey]) {
      return VALUE_ALIASES[lookupKey];
    }
  }

  if (ARABIC_CHAR_REGEX.test(collapsed)) {
    return collapsed;
  }

  if (ALPHANUMERIC_REGEX.test(collapsed) && collapsed.length <= 3) {
    return collapsed.toUpperCase();
  }

  if (/^\d+$/.test(collapsed)) {
    return collapsed;
  }

  return titleCase(collapsed);
};

export const normalizeLabelText = (primary?: string | null, fallback?: string | null): string => {
  const parts = resolveLabelParts(primary, fallback);
  return parts.combined;
};

export const formatSourcePath = (path?: string | null): string => {
  if (!path) {
    return "";
  }
  const normalized = path.replace(/\\/g, "/");
  const artifactsIndex = normalized.indexOf("/artifacts/");
  if (artifactsIndex >= 0) {
    return normalized.slice(artifactsIndex + 1);
  }
  const stageIndex = normalized.indexOf("/stage_");
  if (stageIndex >= 0) {
    return normalized.slice(stageIndex + 1);
  }
  return normalized;
};

export const formatBadgeLabel = (value?: string | null) => normalizeLabelText(value);
