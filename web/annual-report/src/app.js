const state = {
  lang: "zh",
  style: "board_roast",
  rows: [],
  metrics: null,
  narrative: null,
  source: null,
};

const report = document.querySelector("#report");
const statusBox = document.querySelector("#status");
const fileInput = document.querySelector("#fileInput");
const styleSelect = document.querySelector("#styleSelect");
let currentStatus = { en: "Waiting for a file.", zh: "等待上传文件。" };

const staticCopy = {
  eyebrow: { en: "Local-first", zh: "本地优先" },
  appTitle: { en: "Personal Annual Report", zh: "个人年度报告" },
  intro: {
    en: "Upload an Alipay CSV. Your roast report is generated locally in this tab.",
    zh: "上传支付宝 CSV，在本地生成一份可以截图传播的毒舌年报。",
  },
  chooseFile: { en: "Choose Alipay CSV", zh: "选择支付宝 CSV" },
  dropHint: {
    en: "GBK / GB18030 exports are supported. No upload, no login, no API.",
    zh: "支持 GBK / GB18030 编码账单；无上传、无登录、无 API。",
  },
  languageLabel: { en: "Language", zh: "语言" },
  toneLabel: { en: "Tone", zh: "风格" },
  styleBoardRoast: { en: "Board Roast", zh: "毒舌董事会" },
  styleSerious: { en: "Serious Report", zh: "严肃年报" },
  styleSocial: { en: "Social Share", zh: "社交分享短版" },
  exportMarkdown: { en: "Markdown", zh: "导出 MD" },
  exportHtml: { en: "HTML", zh: "导出 HTML" },
  exportPng: { en: "Long PNG", zh: "导出长图" },
  waiting: { en: "Waiting for a file.", zh: "等待上传文件。" },
  placeholderKicker: { en: "Mobile-first. Local-only.", zh: "移动端优先。本地生成。" },
  placeholderTitle: { en: "Your annual roast report will appear here.", zh: "你的年度吐槽报告会显示在这里。" },
  placeholderBody: {
    en: "The product point is the annual-report format and sharper commentary. The ledger parser stays behind the curtain.",
    zh: "核心卖点是年报形式和有记忆点的吐槽；账单解析退到后台。",
  },
};

document.documentElement.dataset.activeLang = state.lang;
document.documentElement.lang = "zh-CN";
applyStaticLanguage();
document.querySelectorAll("[data-lang]").forEach((button) => button.classList.toggle("active", button.dataset.lang === state.lang));

document.querySelectorAll("[data-lang]").forEach((button) => {
  button.addEventListener("click", () => {
    state.lang = button.dataset.lang;
    document.documentElement.dataset.activeLang = state.lang;
    document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-lang]").forEach((item) => item.classList.toggle("active", item === button));
    applyStaticLanguage();
    updateStatus();
    render();
  });
});

styleSelect.addEventListener("change", () => {
  state.style = styleSelect.value;
  if (state.metrics) state.narrative = buildNarrative(state.metrics);
  render();
});

fileInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const text = await readTextFile(file);
    const parsed = file.name.toLowerCase().endsWith(".json")
      ? { rows: parseJson(text), source: "json" }
      : parseUploadedCsv(text, file.name);
    state.source = parsed.source;
    state.rows = cleanRows(normalizeRows(parsed.rows, state.source));
    state.metrics = computeMetrics(state.rows);
    state.narrative = buildNarrative(state.metrics);
    setStatus({
      en: `Loaded ${state.rows.length} rows from ${file.name}. Generated locally.`,
      zh: `已载入 ${state.rows.length} 行：${file.name}。报告已在本地生成。`,
    });
    render();
  } catch (error) {
    console.error(error);
    setStatus({
      en: `Could not parse this file: ${error.message}`,
      zh: `文件解析失败：${error.message}`,
    });
  }
});

document.querySelector("#exportMarkdown").addEventListener("click", () => {
  if (!state.metrics || !state.narrative) return;
  download("personal_annual_report.md", markdownReport(), "text/markdown");
});

document.querySelector("#exportHtml").addEventListener("click", () => {
  if (!state.metrics) return;
  const html = `<!doctype html><meta charset="utf-8"><title>Personal Annual Report</title><style>${getEmbeddedStyles()}</style>${report.outerHTML}`;
  download("personal_annual_report.html", html, "text/html");
});

document.querySelector("#exportPng").addEventListener("click", async () => {
  if (!state.metrics || !state.narrative) return;
  await exportReportPng();
});

async function readTextFile(file) {
  const buffer = await file.arrayBuffer();
  return decodeTextBuffer(buffer);
}

function decodeTextBuffer(buffer) {
  const candidates = [
    { label: "utf-8", fatal: true },
    { label: "gb18030", fatal: false },
    { label: "gbk", fatal: false },
  ];
  for (const candidate of candidates) {
    try {
      const text = new TextDecoder(candidate.label, { fatal: candidate.fatal }).decode(buffer);
      if (candidate.label === "utf-8" || looksReadable(text)) return text;
    } catch {
      // Continue to the next encoding candidate.
    }
  }
  return new TextDecoder("utf-8").decode(buffer);
}

function looksReadable(text) {
  if (text.includes("交易时间") || text.includes("支付宝") || text.includes("收/支")) return true;
  return !text.includes("�");
}

function parseJson(text) {
  const data = JSON.parse(text);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.rows)) return data.rows;
  throw new Error("JSON must be an array or { rows: [...] }.");
}

function parseUploadedCsv(text, fileName) {
  const table = parseCsv(text);
  const source = detectCsvSource(table.headers, fileName);
  if (source === "alipay") {
    return { source, rows: table.rows.map(normalizeAlipayCsvRow) };
  }
  return { source, rows: table.rows };
}

function parseCsv(text) {
  const lines = text.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").filter((line) => line.trim());
  if (!lines.length) return { headers: [], rows: [] };
  const headerIndex = findHeaderIndex(lines);
  const headers = splitCsvLine(lines[headerIndex]).map(cleanCell);
  const rows = [];
  for (const line of lines.slice(headerIndex + 1)) {
    const values = splitCsvLine(line);
    const row = {};
    headers.forEach((header, index) => {
      if (header) row[header] = cleanCell(values[index] ?? "");
    });
    if (Object.values(row).some(Boolean)) rows.push(row);
  }
  return { headers, rows };
}

function splitCsvLine(line) {
  const cells = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    const next = line[i + 1];
    if (char === "\"" && quoted && next === "\"") {
      current += "\"";
      i += 1;
    } else if (char === "\"") {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current);
  return cells;
}

function findHeaderIndex(lines) {
  let bestIndex = 0;
  let bestScore = -1;
  lines.forEach((line, index) => {
    const headers = splitCsvLine(line).map(cleanCell);
    const text = headers.join("|");
    const score = [
      "transaction_time",
      "raw_direction",
      "amount",
      "交易时间",
      "交易创建时间",
      "金额",
      "收/支",
      "交易对方",
      "商品说明",
      "交易状态",
      "交易订单号",
    ].reduce((total, token) => total + (text.includes(token) ? 1 : 0), 0);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function cleanCell(value) {
  return String(value ?? "").replace(/^\uFEFF/, "").trim();
}

function detectCsvSource(headers, fileName) {
  const text = `${fileName} ${headers.join(" ")}`.toLowerCase();
  if (text.includes("alipay") || text.includes("支付宝") || headers.some((header) => ["收/支", "交易对方", "商品说明", "支付宝交易号", "交易订单号"].includes(header))) {
    return "alipay";
  }
  if (headers.includes("source") && headers.includes("normalized_type")) {
    return "cleaned_ledger";
  }
  return "csv_upload";
}

function normalizeRows(rows, sourceHint = null) {
  return rows.map((row, index) => {
    const flow = row.direction || row.raw_direction || row.income_expense || "";
    const amount = numeric(row.amount || row.debit || row.credit || 0);
    const normalizedType = row.normalized_type || inferType(row, flow);
    return {
      source: row.source || sourceHint || inferSource(row.source_file || ""),
      source_file: row.source_file || "browser_upload",
      raw_row_number: row.raw_row_number || String(index + 1),
      transaction_time: row.transaction_time || row.time || row.date || "",
      direction: row.direction || inferDirection(flow, row, normalizedType),
      amount,
      counterparty: row.counterparty || "",
      item_title: row.item_title || row.description || "",
      raw_category: row.raw_category || row.category || row.normalized_type || "",
      payment_method: row.payment_method || "",
      transaction_id: row.transaction_id || row.id || stableBrowserId(row),
      related_transaction_id: row.related_transaction_id || "",
      normalized_type: normalizedType,
      normalized_status: row.normalized_status || inferStatus(normalizedType),
      account_platform: row.account_platform || row.source || sourceHint || "",
      account_name: row.account_name || row.payment_method || "",
      transfer_scope: row.transfer_scope || "external",
      include_in_ledger: row.include_in_ledger || "true",
      needs_review: row.needs_review || "false",
      clean_status: row.clean_status || "active",
      clean_rule: row.clean_rule || "",
    };
  });
}

function normalizeAlipayCsvRow(row) {
  const flow = pick(row, ["raw_direction", "direction", "收/支", "收支"]);
  const rawCategory = pick(row, ["raw_category", "category", "交易分类", "类型"]);
  const status = pick(row, ["status", "交易状态", "状态"]);
  const counterparty = pick(row, ["counterparty", "交易对方", "对方", "商家名称", "收款方"]);
  const itemTitle = pick(row, ["item_title", "商品说明", "商品名称", "交易说明", "备注", "名称"]);
  const paymentMethod = pick(row, ["payment_method", "收/付款方式", "支付方式", "付款方式", "账户", "交易来源地"]);
  const normalizedFlow = normalizeFlow(flow, status);
  return {
    source: "alipay",
    source_file: row.source_file || "browser_upload/alipay.csv",
    raw_row_number: row.raw_row_number || "",
    transaction_time: pick(row, ["transaction_time", "交易时间", "付款时间", "交易创建时间", "创建时间", "最近修改时间", "时间"]),
    raw_direction: normalizedFlow,
    raw_category: rawCategory,
    amount: alipayAmount(row, normalizedFlow),
    status,
    payment_method: paymentMethod,
    counterparty,
    item_title: itemTitle,
    transaction_id: cleanIdentifier(pick(row, ["transaction_id", "交易订单号", "交易号", "支付宝交易号", "商户订单号", "订单号"])) || stableBrowserId(row),
    related_transaction_id: pick(row, ["related_transaction_id", "关联交易号", "原交易号"]),
  };
}

function inferType(row, flow) {
  const typeText = [
    row.raw_category,
    row.category,
    row.counterparty,
    row.item_title,
    row.description,
    row.status,
  ].join(" ");
  const allText = Object.values(row).join(" ");
  const lowerType = typeText.toLowerCase();
  const lowerAll = allText.toLowerCase();
  if (lowerType.includes("repayment") || typeText.includes("还款") || typeText.includes("信用借还")) return "credit_repayment";
  if (typeText.includes("退款") || lowerType.includes("refund")) return "refund_in";
  if (typeText.includes("投资理财") || typeText.includes("基金") || typeText.includes("股票") || typeText.includes("余额宝")) return "investment_flow";
  if (typeText.includes("充值") || typeText.includes("提现") || typeText.includes("转账") || typeText.includes("转入") || typeText.includes("转出")) return "internal_transfer";
  if (flow === "其他") return "neutral_flow";
  if (lowerAll.includes("reward") || lowerAll.includes("campaign") || allText.includes("奖励") || allText.includes("补贴")) return "platform_reward";
  return "merchant_payment";
}

function inferStatus(normalizedType) {
  if (normalizedType === "refund_in") return "refund";
  return "success";
}

function inferDirection(flow, row, normalizedType) {
  if (["neutral_flow", "investment_flow"].includes(normalizedType)) return "neutral";
  if (normalizedType === "refund_in" || normalizedType === "platform_reward" || row.credit || flow === "收入") return "income";
  if (flow === "其他") return "neutral";
  return "expense";
}

function inferSource(sourceFile) {
  const value = sourceFile.toLowerCase();
  return ["alipay", "wechat", "meituan", "douyin", "boc", "cmb", "icbc", "abc"].find((source) => value.includes(source)) || "upload";
}

function pick(row, fields) {
  for (const field of fields) {
    if (row[field] !== undefined && String(row[field]).trim() !== "") {
      return String(row[field]).trim();
    }
  }
  return "";
}

function normalizeFlow(flow, status) {
  const value = `${flow} ${status}`;
  if (value.includes("不计收支") || value.includes("其他") || value.includes("待确认")) return "其他";
  if (value.includes("收入") || value.includes("退款") || value.toLowerCase().includes("refund")) return "收入";
  return "支出";
}

function normalizeAmount(value) {
  const cleaned = String(value || "0")
    .replace(/[￥¥,\s]/g, "")
    .replace(/^收入:/, "")
    .replace(/^支出:/, "")
    .replace(/^\+/, "")
    .replace(/^-/, "");
  return cleaned || "0";
}

function alipayAmount(row, flow) {
  const signedAmount = pick(row, ["amount", "金额", "金额(元)", "金额（元）", "交易金额"]);
  if (signedAmount) return normalizeAmount(signedAmount);
  const income = pick(row, ["收入金额", "收入金额(元)", "收入金额（元）"]);
  const expense = pick(row, ["支出金额", "支出金额(元)", "支出金额（元）"]);
  if (flow === "收入" && income) return normalizeAmount(income);
  if (expense) return normalizeAmount(expense);
  return normalizeAmount(income || expense || "0");
}

function stableBrowserId(row) {
  const seed = [
    pick(row, ["交易时间", "transaction_time", "付款时间", "创建时间"]),
    pick(row, ["交易对方", "counterparty", "商家名称"]),
    pick(row, ["商品说明", "item_title", "商品名称"]),
    pick(row, ["金额", "amount", "金额(元)", "交易金额"]),
  ].join("|");
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return `browser_${hash.toString(16)}`;
}

function cleanIdentifier(value) {
  return String(value || "").replace(/\t/g, "").trim();
}

function cleanRows(rows) {
  return rows.map((row) => {
    const next = { ...row };
    if (["credit_repayment", "personal_repayment"].includes(next.normalized_type)) {
      next.transfer_scope = "debt_repayment";
      next.include_in_ledger = "false";
      next.clean_status = "excluded_credit_repayment";
      next.clean_rule = "repayment_excluded_under_consumption_basis";
    } else if (["wallet_topup", "internal_transfer"].includes(next.normalized_type)) {
      next.transfer_scope = "internal";
      next.include_in_ledger = "false";
      next.clean_status = "excluded_internal_transfer";
      next.clean_rule = "internal_transfer_excluded";
    } else if (next.normalized_type === "investment_flow") {
      next.transfer_scope = "investment";
      next.include_in_ledger = "false";
      next.clean_status = "excluded_investment_flow";
      next.clean_rule = "investment_flow_excluded_from_consumption";
    } else if (next.normalized_type === "neutral_flow") {
      next.transfer_scope = "neutral";
      next.include_in_ledger = "false";
      next.clean_status = "excluded_neutral_flow";
      next.clean_rule = "neutral_flow_excluded_from_consumption";
    }
    return next;
  });
}

function computeMetrics(rows) {
  const expenseRows = rows.filter((row) => row.direction === "expense");
  const includedExpenses = rows.filter((row) => row.direction === "expense" && row.include_in_ledger === "true");
  const incomeRows = rows.filter((row) => row.direction === "income" && row.normalized_type !== "refund_in");
  const refundRows = rows.filter((row) => row.normalized_type === "refund_in");
  const repaymentRows = rows.filter((row) => row.transfer_scope === "debt_repayment");
  const investmentRows = rows.filter((row) => row.transfer_scope === "investment");
  const internalRows = rows.filter((row) => row.transfer_scope === "internal");
  const neutralRows = rows.filter((row) => row.transfer_scope === "neutral");
  const grossExpense = sum(includedExpenses, "amount");
  const refundDeduction = sum(refundRows, "amount");
  const netConsumption = Math.max(0, grossExpense - refundDeduction);
  const grossIncome = sum(incomeRows, "amount");
  const repaymentTotal = sum(repaymentRows, "amount");
  const investmentTotal = sum(investmentRows, "amount");
  const internalTransferTotal = sum(internalRows, "amount");
  const neutralTotal = sum(neutralRows, "amount");
  const categoryTotals = groupByAmount(includedExpenses, (row) => displayCategory(row.raw_category || row.normalized_type || "uncategorized"));
  const counterpartyTotals = groupByAmount(includedExpenses, (row) => row.counterparty || "unknown");
  const paymentTotals = groupByAmount(includedExpenses, (row) => row.payment_method || "unknown");
  const topCategories = topEntries(categoryTotals, 5);
  const topCounterparties = topEntries(counterpartyTotals, 5);
  const topPaymentMethods = topEntries(paymentTotals, 3);
  const largestExpense = [...includedExpenses].sort((a, b) => b.amount - a.amount)[0] || null;
  const smallSpendCount = includedExpenses.filter((row) => row.amount > 0 && row.amount <= 20).length;
  const activeDays = new Set(rows.map((row) => row.transaction_time.slice(0, 10)).filter(Boolean)).size;
  const topCategory = topCategories[0] || { label: "n/a", value: 0 };
  const concentration = netConsumption ? topCategory.value / netConsumption : 0;
  const dateRange = inferDateRange(rows);
  return {
    rows,
    totalRows: rows.length,
    expenseRows: expenseRows.length,
    includedExpenses,
    incomeRows,
    refundRows,
    repaymentRows,
    investmentRows,
    internalRows,
    neutralRows,
    grossIncome,
    grossExpense,
    refundDeduction,
    netConsumption,
    netCashflow: grossIncome - grossExpense,
    repaymentTotal,
    investmentTotal,
    internalTransferTotal,
    neutralTotal,
    topCategories,
    topCounterparties,
    topPaymentMethods,
    largestExpense,
    smallSpendCount,
    activeDays,
    concentration,
    dateRange,
  };
}

const ZH_TEMPLATE_BANK = {
  categoryRoasts: [
    {
      match: ["餐饮", "美食", "食品"],
      headlines: [
        "{top}成为年度第一大股东",
        "预算部已申请餐饮冷静期",
        "胃口的战略定力强于预算纪律",
        "{top}拿下年度主菜位置",
        "吃点好的完成规模化扩张",
        "{top}把生活质量写进主营业务",
        "饭点成了现金流的高峰时段",
        "{top}负责把年度剧情推向饭桌",
        "管理层对口腹之欲执行力稳定",
        "餐饮分部拥有稳定复购能力",
      ],
      discussions: [
        "“吃点好的”执行得很坚决，问题是财务部没有提前收到通知。",
        "每一顿都像合理消费，合在一起开始像一份专项预算。",
        "管理层用味觉证明生活还在继续，账单用数字证明它确实继续得很努力。",
        "该分部复购能力优秀，审计委员会建议同步披露饭后悔意。",
        "消费动机通常写作“犒劳自己”，财务影响读作“又来一次”。",
        "本期餐饮支出具备稳定性、连续性，以及让预算部门沉默的能力。",
        "如果这是长期战略，董事会建议至少给它配一份年度预算。",
        "管理层把饭点当成经营节点，现金流只能被动参会。",
      ],
    },
    {
      match: ["交通", "出行", "打车", "地铁"],
      headlines: [
        "{top}把年度剧情开到了路上",
        "钱包跟着行程一起移动",
        "管理层用位移制造经营进展",
        "{top}负责证明生活没有原地踏步",
        "出行效率提升，现金流同步提速",
        "{top}成为年度移动成本中心",
        "路线规划很清楚，预算路线略失控",
        "人生在路上，账单也在路上",
      ],
      discussions: [
        "移动效率看起来提升了，预算部门只看到钱在加速离场。",
        "每一次出发都有理由，合计后像现金流在跑耐力赛。",
        "管理层完成了地理位移，财务部完成了心理位移。",
        "出行支出具备刚需外观，董事会仍建议复核打车冲动。",
        "该分部证明了抵达很重要，也证明了抵达可以很贵。",
        "路线由地图规划，预算由账单事后教育。",
        "如果把通勤也算经营活动，本期经营活动相当活跃。",
        "现金流随行程波动，审计委员会建议少用赶时间作为万能理由。",
      ],
    },
    {
      match: ["日用", "百货", "生活", "家居"],
      headlines: [
        "{top}用合理外表完成规模扩张",
        "小额采购拿下高存在感",
        "生活稳定性提升，账单厚度同步提升",
        "{top}把必要支出做成连续剧",
        "预算部最难反驳的分部出现了",
        "每笔都正常，合计很有意见",
        "{top}正在安静扩表",
        "生活细节负责蚕食预算",
      ],
      discussions: [
        "每笔都像生活必需，合计后像生活在和预算谈判。",
        "日用支出最会装作背景音，月底合计时突然开始领唱。",
        "管理层很难否认它有必要，董事会也很难忽略它有规模。",
        "本分部的战术是低调出现、高频成交、月底发言。",
        "生活品质的确需要维护，维护成本也确实很会长大。",
        "采购理由通常很朴素，累计结果一点也不朴素。",
        "如果预算有防线，日用百货通常从门缝里进来。",
        "该分部缺少戏剧性，但不缺持续伤害。",
      ],
    },
    {
      match: ["文化", "休闲", "娱乐", "影视", "书", "音乐"],
      headlines: [
        "{top}负责给现金流上审美课",
        "精神生活获得投入，预算获得教育",
        "审美建设打开了预算的窗",
        "{top}把快乐写成了费用",
        "文化休闲提交了精神资产申请",
        "快乐有价格，账单有证据",
        "{top}负责证明人不能只活在报表里",
        "精神消费跑出了存在感",
      ],
      discussions: [
        "精神生活值得投入，审计委员会只想知道这份快乐有没有复购必要。",
        "管理层把快乐计入生活质量，预算部把它计入待解释事项。",
        "该分部拥有叙事价值，财务价值仍需更多证据。",
        "文化休闲不负责赚钱，只负责让账单看起来有灵魂。",
        "如果情绪价值能折旧，本期资产负债表会好看一点。",
        "快乐本身没有问题，账单只是提醒它很会按次收费。",
        "本期审美建设积极，现金流接受了被建设。",
        "精神资产暂未入表，现金支出已经入账。",
      ],
    },
    {
      match: ["运动", "户外", "健身"],
      headlines: [
        "{top}上线，钱包先完成热身",
        "管理层用运动证明自律，账单保留证据",
        "身体治理很积极，出勤率等待披露",
        "{top}把自律写进费用科目",
        "健康投资率先消耗现金流",
        "身体开始营业，预算开始冒汗",
        "{top}提交了自我管理申请",
        "运动分部看起来很有上进心",
      ],
      discussions: [
        "运动支出很像自律宣言，董事会建议把实际出勤率一起披露。",
        "管理层为健康投入现金，审计委员会等待身体交付成果。",
        "如果运动次数跟付款次数一致，本期治理水平会非常优秀。",
        "本分部值得鼓励，也值得要求 KPI。",
        "健康当然重要，账单只是希望它别只停留在装备层面。",
        "身体治理的第一步是付款，第二步最好真的出门。",
        "运动支出具备正当性，复核重点在执行率。",
        "管理层买下的是可能性，董事会想看的是使用率。",
      ],
    },
    {
      match: ["服饰", "鞋", "美妆", "护肤"],
      headlines: [
        "{top}推动形象管理扩容",
        "{top}让现金流配合营业",
        "外观治理成为重点项目",
        "管理层对体面投入稳定",
        "{top}负责把自我呈现做成成本中心",
        "形象管理拿到了预算发言权",
        "体面很重要，账单很直接",
        "{top}提交了审美升级方案",
      ],
      discussions: [
        "形象管理当然有价值，董事会只是想确认价值有没有被尺码和色号稀释。",
        "管理层对“看起来更好”的定义持续扩容，预算部正在追认。",
        "该分部擅长把欲望包装成必要升级。",
        "如果体面能产生现金流，本期估值会更友好。",
        "本分部的核心风险是：每次都差一点就完整了。",
        "外观治理有成果，财务治理还在路上。",
        "审美升级可以理解，重复升级需要解释。",
        "该分部不缺理由，缺的是上限。",
      ],
    },
    {
      match: ["数码", "电子", "电脑", "手机", "设备"],
      headlines: [
        "{top}申请成为生产力投资",
        "设备升级拿到年度剧情",
        "生产力叙事再次上线",
        "{top}把效率写进采购理由",
        "管理层相信新设备能带来新人生",
        "科技感提升，现金流下降",
        "{top}负责制造升级幻觉",
        "效率工具首先提高了付款效率",
      ],
      discussions: [
        "生产力工具当然重要，董事会只想知道生产力本人到岗没有。",
        "设备升级的理由很充分，充分到预算部不敢马上反驳。",
        "如果新设备能自动回本，本报告愿意补发喜报。",
        "管理层购买的是效率预期，账单记录的是现金现实。",
        "科技改善生活，也改善了商家的收入确认。",
        "本分部适合建立验收制度，防止每次升级都停在开箱阶段。",
        "效率叙事很动人，财务影响很具体。",
        "该分部最大风险是把工具误写成成果。",
      ],
    },
    {
      match: ["医疗", "健康", "药", "医院"],
      headlines: [
        "{top}提醒管理层身体也会开票",
        "健康分部拥有最高解释权",
        "{top}把现实感带回报表",
        "身体发来付款通知",
        "健康成本进入董事会视野",
        "管理层收到生理层面的审计意见",
      ],
      discussions: [
        "这类支出不适合玩笑化，董事会只建议管理层早点预防，少点临时抢修。",
        "健康支出具有刚性，预算部无权阴阳怪气。",
        "本分部提醒管理层：身体也是长期资产。",
        "支出可以记录，健康状态仍需本人持续维护。",
        "审计委员会建议把预防性投入提前，少等身体亲自发函。",
        "该分部的目标很简单：少花冤枉钱，多保长期经营。",
      ],
    },
  ],
  verdicts: [
    "董事会认为，本年度主体仍具备持续经营能力，前提是管理层停止把每一笔支出包装成“生活质量投资”。",
    "管理层展示了稳定的付款能力，也展示了同样稳定的自我说服能力。审计委员会已记录在案。",
    "本年度现金流没有失控，主要得益于账单系统足够诚实，及时暴露了管理层的若干幻觉。",
    "公司治理结构完整：消费负责冲锋，还款负责回头补刀，退款负责提供一点体面。",
    "董事会建议下年度继续经营，但采购部门需要少开几场没有预算的临时会议。",
    "本期最大亮点是账本愿意说实话，最大风险是管理层听完仍然下单。",
    "管理层保持了对生活的热爱，也保持了对预算边界的试探。",
    "审计委员会确认：本年度没有发现魔法，只有付款、解释付款和重新解释付款。",
  ],
  mda: [
    "报告期内，净消费为 {net}。管理层声称这些支出改善了生活，董事会要求其提供更多证据。",
    "公司全年主要经营活动围绕付款、解释付款、忘记付款理由展开。分类工作完成后，部分消费的战略意义出现明显下修。",
    "净消费 {net} 构成本年度主营业务成本。它没有形成护城河，最多形成了一些聊天素材。",
    "收入端录得 {income}，消费端录得 {expense}。两端都很努力，方向感由审计委员会另行评估。",
    "报告期内，消费活动具备连续性和创造力，预算纪律仍处于试运行阶段。",
    "管理层对年度生活质量有清晰追求，对年度预算上限缺少同等尊重。",
    "本报告确认：消费动机通常很饱满，财务结果通常很具体。",
    "公司没有披露完整资产负债表，但消费行为已经充分披露管理层性格。",
  ],
  quotes: [
    "预算最大的敌人，通常披着‘就这一次’的外衣。",
    "退款很难算赚钱，最多算管理层给错误打了个折。",
    "还款单独列示，顺便提醒消费曾经真实存在。",
    "小额支出最会装无辜，合计数最会说实话。",
    "生活质量可以提高，采购流程也该同步提高。",
    "当账单开始讲故事，董事会最好先坐下。",
    "小票会消失，账单会复述。",
    "预算没有情绪，但账单很会补刀。",
    "所有‘不贵’加起来，都会变得很有话语权。",
    "管理层可以忘记理由，流水不会。",
  ],
  fallbackHeadlines: [
    "{top}拿下第一大分部",
    "{top}贡献了年度主线",
    "预算部门正在复核{top}的必要性",
    "{top}进入董事会重点观察名单",
    "{top}成为现金流的主要去向",
    "{top}获得年度存在感奖",
  ],
  fallbackDiscussions: [
    "{top}以 {amount} 的规模进入视野，管理层需要解释这条主线为何如此花钱。",
    "{top}坐上榜首，预算部门目前情绪稳定，主要因为它还没来得及反应。",
    "{top}具备明确存在感，董事会建议下期设置预算护栏。",
    "该分部的消费理由较为分散，合计结果非常团结。",
  ],
};

function buildNarrative(metrics) {
  const flags = {
    zero: metrics.netConsumption === 0,
    repaymentHeavy: metrics.repaymentTotal > metrics.netConsumption * 0.4 && metrics.repaymentTotal > 0,
    refundHeavy: metrics.refundDeduction > metrics.grossExpense * 0.08 && metrics.refundDeduction > 0,
    investmentHeavy: metrics.investmentTotal > metrics.netConsumption && metrics.investmentTotal > 0,
    concentrated: metrics.concentration > 0.45,
    manySmall: metrics.smallSpendCount >= Math.max(8, metrics.includedExpenses.length * 0.25),
    neutralHeavy: metrics.neutralRows.length > metrics.includedExpenses.length,
  };
  const persona = choosePersona(metrics, flags);
  const zh = buildZhNarrative(metrics, flags, persona);
  const en = buildEnNarrative(metrics, flags, persona);
  applyNarrativeStyle(zh, en, metrics, flags);
  return { zh, en, flags, persona };
}

function applyNarrativeStyle(zh, en, metrics, flags) {
  if (state.style === "serious") {
    zh.persona = "本地账本观察者";
    zh.verdict = `报告期内净消费 ${moneyText(metrics.netConsumption)}，退款、还款、投资及中性流已单独列示。`;
    zh.mda = `收入端 ${moneyText(metrics.grossIncome)}，退款前支出 ${moneyText(metrics.grossExpense)}，退款抵扣 ${moneyText(metrics.refundDeduction)}。本报告以消费口径为主，资产余额待后续版本接入。`;
    zh.segment = `${metrics.topCategories[0]?.label || "未命名分部"} 为本期第一大消费分部，金额 ${moneyText(metrics.topCategories[0]?.value || 0)}。`;
    zh.segmentHeadline = `主要消费分部：${metrics.topCategories[0]?.label || "未命名分部"}`;
    zh.segmentMeta = `${moneyText(metrics.topCategories[0]?.value || 0)} · 占退款前支出 ${percentText(metrics.topCategories[0]?.value || 0, metrics.grossExpense)}`;
    zh.audit = "本地浏览器生成，无上传、无登录、无 API。";
    zh.quote = "账单的价值，在于让现金流有据可查。";
    zh.categoryRoast = `${metrics.topCategories[0]?.label || "第一大分部"} 为主要消费分部，后续可结合预算目标进一步分析。`;
    zh.cashflowRoast = `还款、投资及中性流已单独列示，避免消费口径被账户流动放大。`;
    zh.boardQuestions = [
      "是否需要为主要消费分部设置预算上限？",
      "退款是否代表消费决策存在可前置优化空间？",
      "还款与投资流量是否需要在完整账本中继续配对核验？",
      "是否需要补充余额快照以生成资产负债表？",
    ];

    en.persona = "Local Ledger Observer";
    en.verdict = `Net consumption was ${moneyText(metrics.netConsumption)} with refunds, repayments, investment flow, and neutral flow separated.`;
    en.mda = `Income was ${moneyText(metrics.grossIncome)}, gross expense was ${moneyText(metrics.grossExpense)}, and refund recovery was ${moneyText(metrics.refundDeduction)}.`;
    en.segment = `${metrics.topCategories[0]?.label || "Unnamed segment"} was the largest consumption segment at ${moneyText(metrics.topCategories[0]?.value || 0)}.`;
    en.segmentHeadline = `Main segment: ${metrics.topCategories[0]?.label || "Unnamed segment"}`;
    en.segmentMeta = `${moneyText(metrics.topCategories[0]?.value || 0)} · ${percentText(metrics.topCategories[0]?.value || 0, metrics.grossExpense)} of gross expense`;
    en.audit = "Generated locally in browser memory. No upload, no login, no API.";
    en.quote = "A personal ledger is useful when cash flow becomes traceable.";
    en.categoryRoast = `${metrics.topCategories[0]?.label || "The largest segment"} was the main consumption segment for this period.`;
    en.cashflowRoast = "Repayments, investment flow, and neutral flow are separated to keep the consumption view clean.";
    en.boardQuestions = [
      "Should the largest segment get a budget limit?",
      "Can refund recovery move earlier into purchase discipline?",
      "Do repayments and investment flows need ledger-level pairing?",
      "Would a balance snapshot enable a real balance sheet?",
    ];
  }

  if (state.style === "social_share") {
    const top = metrics.topCategories[0]?.label || "未命名分部";
    zh.title = "我的账单年报";
    zh.persona = flags.repaymentHeavy ? "旧账追着跑选手" : "预算边缘试探选手";
    zh.verdict = `今年花掉 ${moneyText(metrics.netConsumption)}，${top}负责把年度剧情推向高潮。`;
    zh.mda = `还款 ${moneyText(metrics.repaymentTotal)} 单独亮相，退款 ${moneyText(metrics.refundDeduction)} 负责给场面降温。`;
    zh.segment = `${top} 坐上第一大分部，董事会表情复杂。`;
    zh.segmentHeadline = `年度第一名：${top}`;
    zh.segmentMeta = `${moneyText(metrics.topCategories[0]?.value || 0)} · 占退款前支出 ${percentText(metrics.topCategories[0]?.value || 0, metrics.grossExpense)}`;
    zh.audit = "浏览器本地生成，适合截图，尴尬自理。";
    zh.quote = "小票会消失，账单会复述。";
    zh.categoryRoast = `${top}拿下第一名，预算部门正在假装没看见。`;
    zh.cashflowRoast = `还款 ${moneyText(metrics.repaymentTotal)} 负责提醒过去，退款 ${moneyText(metrics.refundDeduction)} 负责抢救现在。`;
    zh.boardQuestions = [
      `${top}下次能不能先写申请？`,
      "退款能不能提前发生在下单前？",
      "还款提醒出现时，管理层能不能少装惊讶？",
      "小额支出能不能停止集体装路人？",
    ];

    en.title = "My Ledger Wrapped";
    en.persona = flags.repaymentHeavy ? "Chased by Old Bills" : "Budget Boundary Tester";
    en.verdict = `Net consumption: ${moneyText(metrics.netConsumption)}. ${top} carried the plot.`;
    en.mda = `Repayments stood at ${moneyText(metrics.repaymentTotal)}; refunds recovered ${moneyText(metrics.refundDeduction)}.`;
    en.segment = `${top} won the segment race. The board has follow-up questions.`;
    en.segmentHeadline = `Winner: ${top}`;
    en.segmentMeta = `${moneyText(metrics.topCategories[0]?.value || 0)} · ${percentText(metrics.topCategories[0]?.value || 0, metrics.grossExpense)} of gross expense`;
    en.audit = "Generated locally. Screenshot-friendly, API-free.";
    en.quote = "Receipts fade. Ledgers remember.";
    en.categoryRoast = `${top} took first place. Budget control is pretending not to notice.`;
    en.cashflowRoast = `Repayments remember the past; refunds tried to rescue the present.`;
    en.boardQuestions = [
      `Can ${top} file a request next time?`,
      "Can refunds happen before checkout?",
      "Can management stop acting surprised by repayments?",
      "Can small purchases stop pretending to be background noise?",
    ];
  }
}

function choosePersona(metrics, flags) {
  if (flags.zero) return { zh: "零支出 CFO", en: "Zero-Spend CFO" };
  if (flags.repaymentHeavy) return { zh: "还款追偿型董事长", en: "Repayment-Chased Chair" };
  if (flags.investmentHeavy) return { zh: "理财剧情推动者", en: "Portfolio Drama Operator" };
  if (flags.manySmall) return { zh: "小额高频采购部", en: "High-Frequency Procurement Desk" };
  if (flags.concentrated) return { zh: "单一分部信仰者", en: "Single-Segment Loyalist" };
  return { zh: "分散型家庭小公司", en: "Diversified Household Small Cap" };
}

function buildZhCategoryRoast(metrics) {
  const top = metrics.topCategories[0]?.label || "未命名分部";
  const amount = moneyText(metrics.topCategories[0]?.value || 0);
  const templates = findZhCategoryTemplates(top)?.headlines || ZH_TEMPLATE_BANK.fallbackHeadlines;
  return fillTemplate(pickByHash(templates, top.length + Math.round(metrics.netConsumption)), {
    top,
    amount,
    share: percentText(metrics.topCategories[0]?.value || 0, metrics.netConsumption),
  });
}

function buildZhCashflowRoast(metrics, flags) {
  const top = metrics.topCategories[0]?.label || "第一大分部";
  const amount = moneyText(metrics.topCategories[0]?.value || 0);
  const options = [];
  const categoryDiscussions = findZhCategoryTemplates(top)?.discussions || ZH_TEMPLATE_BANK.fallbackDiscussions;
  options.push(fillTemplate(pickByHash(categoryDiscussions, metrics.totalRows + top.length), {
    top,
    amount,
    share: percentText(metrics.topCategories[0]?.value || 0, metrics.netConsumption),
  }));
  if (flags.repaymentHeavy) options.push(`还款 ${moneyText(metrics.repaymentTotal)} 单独列示，旧消费换了个时间点回来收尾款。`);
  if (flags.investmentHeavy) options.push(`投资及中性流合计 ${moneyText(metrics.investmentTotal + metrics.neutralTotal)}，这条剧情不算消费，但足够让报表看起来很忙。`);
  if (flags.refundHeavy) options.push(`退款挽回 ${moneyText(metrics.refundDeduction)}，管理层终于展示了一点反悔能力。`);
  if (metrics.smallSpendCount > 10) options.push(`小额支出共 ${metrics.smallSpendCount} 笔，它们单独出现时很乖，排队汇总时很会顶嘴。`);
  const fallback = [
    `现金流整体可追踪，主要问题仍在采购动机披露不足。`,
    `本期账本秩序尚可，若管理层继续稳定发挥，下期吐槽素材供应无忧。`,
    `经营活动具备连续性，预算纪律仍处于需要人工复核的阶段。`,
  ];
  return options[0] || pickByHash(fallback, metrics.totalRows);
}

function findZhCategoryTemplates(category) {
  return ZH_TEMPLATE_BANK.categoryRoasts.find((item) => item.match.some((token) => category.includes(token)));
}

function fillTemplate(template, values) {
  return String(template).replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

function buildZhBoardQuestions(metrics) {
  const top = metrics.topCategories[0]?.label || "第一大分部";
  const largest = metrics.largestExpense;
  const questions = [
    `${top} 是否已经从“偶发支出”升级为“核心业务”？`,
    `退款项目能否前置为购买前的冷静期，别总等到事后挽回体面？`,
    `还款压力是否来自真实刚需，还是来自过去的管理层激情发言？`,
    `小额支出是否需要设立专门委员会，防止它们继续伪装成背景噪音？`,
    largest ? `${largest.counterparty || "最大单笔交易对方"} 这笔 ${moneyText(largest.amount)} 的采购，是否已经完成价值验收？` : `最大单笔交易暂缺，董事会暂时失去一个重点审问对象。`,
  ];
  return questions.slice(0, 4);
}

function buildZhNarrative(metrics, flags, persona) {
  const top = metrics.topCategories[0]?.label || "未命名分部";
  const topAmount = metrics.topCategories[0]?.value || 0;
  const topShare = percentText(topAmount, metrics.grossExpense);
  const largest = metrics.largestExpense;
  const categoryRoast = buildZhCategoryRoast(metrics);
  const cashflowRoast = buildZhCashflowRoast(metrics, flags);
  const boardQuestions = buildZhBoardQuestions(metrics);
  const flagVerdicts = [];
  if (flags.repaymentHeavy) flagVerdicts.push(`还款金额达到 ${moneyText(metrics.repaymentTotal)}，过去的消费带着日程提醒回来敲门。`);
  if (flags.investmentHeavy) flagVerdicts.push(`投资理财流量达到 ${moneyText(metrics.investmentTotal)}，资本市场戏份很足，现金流在旁边鼓掌。`);
  if (flags.refundHeavy) flagVerdicts.push(`退款收回 ${moneyText(metrics.refundDeduction)}，盈利能力暂未确认，撤退能力已经通过压力测试。`);
  if (flags.manySmall) flagVerdicts.push(`小额交易数量偏高，采购部疑似用碎片化支出训练耐心。`);
  const verdict = flagVerdicts[0] || pickByHash(ZH_TEMPLATE_BANK.verdicts, metrics.totalRows + Math.round(metrics.netConsumption));
  const mdaPool = ZH_TEMPLATE_BANK.mda.map((template) => fillTemplate(template, {
    net: moneyText(metrics.netConsumption),
    income: moneyText(metrics.grossIncome),
    expense: moneyText(metrics.grossExpense),
  }));
  const segmentPool = [
    `${top} 成为第一大消费分部，金额 ${moneyText(topAmount)}。该部门对预算的影响力已经超过部分管理层成员。`,
    `${top} 以 ${moneyText(topAmount)} 的规模进入董事会视野，建议下年度接受更严格的绩效问询。`,
    `${top} 本期存在感强烈。若继续扩张，建议单独设立事业部并配备道歉模板。`,
  ];
  const auditPool = [
    `审计师提醒：账单会记住管理层忘掉的理由。`,
    `本报告不评价消费品味，只评价消费留下的证据。证据目前比较健谈。`,
    `由于缺少余额快照，本报告无法确认资产负债表，只能确认若干支出确实来过。`,
    `本地生成，无上传记录。数据留在浏览器，尴尬留给董事会。`,
  ];
  const quotePool = ZH_TEMPLATE_BANK.quotes;
  const risks = [
    flags.repaymentHeavy ? `还款压力偏高：${moneyText(metrics.repaymentTotal)} 的历史消费正在申请复议。` : `还款项目已单独列示，避免把旧账重复算成新消费。`,
    flags.investmentHeavy ? `投资理财流量较大：${moneyText(metrics.investmentTotal)} 不计入消费，但足以影响年度剧情。` : `投资理财流量已从消费中剥离，避免把资产流动写成购物故事。`,
    flags.concentrated ? `${top} 集中度较高，单一分部已经具备左右年度叙事的能力。` : `消费分部较分散，暂未发现单一部门独揽骂名。`,
    metrics.neutralRows.length ? `不计收支 ${metrics.neutralRows.length} 笔，属于账本里的灰色会议室。` : `不计收支项目较少，报表暂时没有太多暗门。`,
  ];
  const highlights = [
    { label: "净消费", value: moneyText(metrics.netConsumption), note: "退款后口径" },
    { label: "已排除还款", value: moneyText(metrics.repaymentTotal), note: "历史消费回访" },
    { label: "退款挽回", value: moneyText(metrics.refundDeduction), note: "撤退也算治理" },
    { label: "投资/中性流", value: moneyText(metrics.investmentTotal + metrics.neutralTotal), note: "剧情线另列" },
  ];
  return {
    title: "个人年度报告",
    subtitle: `${metrics.dateRange} · 本地生成 · 支付宝账单口径`,
    persona: persona.zh,
    verdict,
    mda: flagVerdicts[1] || pickByHash(mdaPool, Math.round(metrics.grossExpense)),
    segment: pickByHash(segmentPool, top.length + Math.round(topAmount)),
    segmentHeadline: `第一大分部：${top}`,
    segmentMeta: `${moneyText(topAmount)} · 占退款前支出 ${topShare}`,
    audit: pickByHash(auditPool, metrics.totalRows),
    quote: pickByHash(quotePool, Math.round(metrics.netConsumption + metrics.repaymentTotal)),
    risks,
    highlights,
    categoryRoast,
    cashflowRoast,
    boardQuestions,
    largest: largest ? `最大单笔支出：${largest.counterparty || "未知对方"}，${moneyText(largest.amount)}。董事会建议回忆一下当时的雄心。` : "未发现可列示的消费支出。",
  };
}

function buildEnNarrative(metrics, flags, persona) {
  const top = metrics.topCategories[0]?.label || "unnamed segment";
  const topAmount = metrics.topCategories[0]?.value || 0;
  const largest = metrics.largestExpense;
  return {
    title: "Personal Annual Report",
    subtitle: `${metrics.dateRange} · generated locally · Alipay CSV view`,
    persona: persona.en,
    verdict: flags.repaymentHeavy
      ? `Repayments reached ${moneyText(metrics.repaymentTotal)}. Prior spending returned with a calendar invite.`
      : "The board finds the entity traceable, solvent in ledger view, and occasionally too generous to its own spending thesis.",
    mda: `Net consumption was ${moneyText(metrics.netConsumption)} after refund recovery. Management may call this lifestyle investment; the audit committee requests evidence.`,
    segment: `${top} led segment performance. Dominance in a personal ledger is influence, not a moat.`,
    segmentHeadline: `Largest segment: ${top}`,
    segmentMeta: `${moneyText(topAmount)} · ${percentText(topAmount, metrics.grossExpense)} of gross expense`,
    audit: "Generated locally from browser memory. No upload, no login, no API.",
    quote: "The bill remembers what management rebranded as strategy.",
    risks: [
      `Repayments excluded from new consumption: ${moneyText(metrics.repaymentTotal)}.`,
      `Investment and neutral flows separated: ${moneyText(metrics.investmentTotal + metrics.neutralTotal)}.`,
      `Refund recovery: ${moneyText(metrics.refundDeduction)}.`,
      `Rows parsed: ${metrics.totalRows}.`,
    ],
    highlights: [
      { label: "Net consumption", value: moneyText(metrics.netConsumption), note: "after refunds" },
      { label: "Repayments", value: moneyText(metrics.repaymentTotal), note: "excluded" },
      { label: "Refunds", value: moneyText(metrics.refundDeduction), note: "recovered" },
      { label: "Investment flow", value: moneyText(metrics.investmentTotal), note: "separate story" },
    ],
    categoryRoast: `${top} became the largest segment. The board accepts the data and reserves judgment on the taste.`,
    cashflowRoast: flags.repaymentHeavy
      ? `Repayments of ${moneyText(metrics.repaymentTotal)} show that old consumption still knows how to schedule a follow-up.`
      : `Cash flow is traceable; procurement motives remain under-documented.`,
    boardQuestions: [
      `Has ${top} become a core business line?`,
      `Can refund recovery move earlier into purchase discipline?`,
      `Do small purchases need their own governance committee?`,
      largest ? `Did the largest purchase at ${moneyText(largest.amount)} pass value inspection?` : `No largest purchase was identified for review.`,
    ],
    largest: largest ? `Largest purchase: ${largest.counterparty || "unknown"}, ${moneyText(largest.amount)}.` : "No included purchase found.",
  };
}

function render() {
  if (!state.metrics || !state.narrative) return;
  document.body.classList.toggle("has-report", true);
  const copy = state.narrative[state.lang];
  const metrics = state.metrics;
  const topCategories = metrics.topCategories.length ? metrics.topCategories : [{ label: "n/a", value: 0 }];
  const maxCategory = Math.max(...topCategories.map((item) => item.value), 1);
  report.innerHTML = `
    <div class="annual-stack">
      <section class="report-card cover-card">
        <p class="eyebrow">${escapeHtml(copy.subtitle)}</p>
        <h2 class="cover-title">${escapeHtml(copy.title)}</h2>
        <p class="cover-verdict">${escapeHtml(copy.verdict)}</p>
        <p class="privacy-line">${escapeHtml(t("Local only. Your file does not leave this browser tab.", "本地生成。文件不会离开当前浏览器标签页。"))}</p>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Board Verdict", "董事会结论"))}</p>
        <h3 class="card-title">${escapeHtml(copy.persona)}</h3>
        <p class="roast">${escapeHtml(copy.mda)}</p>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Financial Highlights", "财务摘要"))}</p>
        <div class="big-number">${escapeHtml(moneyText(metrics.netConsumption))}</div>
        <p class="muted">${escapeHtml(t("Net consumption after refund recovery", "退款抵扣后的净消费"))}</p>
        <div class="mini-grid">
          ${copy.highlights.map((item) => miniMetric(item.label, item.value, item.note)).join("")}
        </div>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Personal Income Statement", "个人利润表"))}</p>
        <h3 class="card-title">${escapeHtml(t("Simplified Statement", "简化报表"))}</h3>
        <div class="statement">
          ${statementRow(t("Income", "收入"), moneyText(metrics.grossIncome))}
          ${statementRow(t("Gross expense", "退款前总支出"), moneyText(metrics.grossExpense))}
          ${statementRow(t("Refund recovery", "退款挽回"), moneyText(metrics.refundDeduction))}
          ${statementRow(t("Net consumption", "净消费"), moneyText(metrics.netConsumption))}
          ${statementRow(t("Repayment excluded", "已排除还款"), moneyText(metrics.repaymentTotal))}
          ${statementRow(t("Investment / neutral flow", "投资及中性流"), moneyText(metrics.investmentTotal + metrics.neutralTotal))}
        </div>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Segment Performance", "分部表现"))}</p>
        <div class="segment-summary">
          <h3 class="segment-title">${escapeHtml(t("Largest Segment", "第一大分部"))}</h3>
          <div class="segment-hero">
            <span>${escapeHtml(topCategories[0].label)}</span>
            <strong>${escapeHtml(moneyText(topCategories[0].value))}</strong>
          </div>
          <p class="segment-meta">${escapeHtml(copy.segmentMeta || "")}</p>
        </div>
        <div class="bar-list compact-bars">
          ${topCategories.map((item, index) => barRow(item.label, item.value, maxCategory, index, metrics.grossExpense)).join("")}
        </div>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Management Discussion", "管理层讨论"))}</p>
        <h3 class="discussion-title">${escapeHtml(copy.categoryRoast)}</h3>
        <p class="roast secondary-roast">${escapeHtml(copy.cashflowRoast)}</p>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Largest Purchase", "最大单笔"))}</p>
        <p class="roast">${escapeHtml(copy.largest)}</p>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Risk Factors", "风险因素"))}</p>
        <h3 class="card-title">${escapeHtml(t("Audit Committee Notes", "审计委员会备注"))}</h3>
        <ul class="risk-list">
          ${copy.risks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </section>

      <section class="report-card">
        <p class="card-kicker">${escapeHtml(t("Board Questions", "董事会追问"))}</p>
        <ul class="question-list">
          ${copy.boardQuestions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </section>

      <section class="report-card share-card">
        <p class="card-kicker">${escapeHtml(t("Annual Line", "年度金句"))}</p>
        <div class="quote-mark">“</div>
        <h3 class="card-title">${escapeHtml(copy.quote)}</h3>
        <p class="muted">${escapeHtml(copy.audit)}</p>
      </section>
    </div>
  `;
}

function miniMetric(label, value, note) {
  return `<article class="mini-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><span>${escapeHtml(note)}</span></article>`;
}

function statementRow(label, value) {
  return `<div class="statement-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function barRow(label, value, max, index = 0, total = 0) {
  const width = max ? Math.max(4, (value / max) * 100) : 0;
  const share = percentText(value, total);
  return `
    <div class="bar-row">
      <div class="bar-top">
        <span><b>#${index + 1}</b>${escapeHtml(label)}</span>
        <span>${escapeHtml(moneyText(value))}<small>${escapeHtml(share)}</small></span>
      </div>
      <div class="bar"><span style="width: ${width}%"></span></div>
    </div>`;
}

function markdownReport() {
  const copy = state.narrative[state.lang];
  const metrics = state.metrics;
  return [
    `# ${copy.title}`,
    "",
    copy.subtitle,
    "",
    `## ${t("Board Verdict", "董事会结论")}`,
    "",
    copy.verdict,
    "",
    `## ${t("Financial Highlights", "财务摘要")}`,
    "",
    `- ${t("Net consumption", "净消费")}: ${moneyText(metrics.netConsumption)}`,
    `- ${t("Refund recovery", "退款挽回")}: ${moneyText(metrics.refundDeduction)}`,
    `- ${t("Repayment excluded", "已排除还款")}: ${moneyText(metrics.repaymentTotal)}`,
    `- ${t("Investment / neutral flow", "投资及中性流")}: ${moneyText(metrics.investmentTotal + metrics.neutralTotal)}`,
    "",
    `## ${t("Annual Line", "年度金句")}`,
    "",
    copy.quote,
    "",
  ].join("\n");
}

async function exportReportPng() {
  try {
    const pngUrl = await renderReportElementToPng();
    downloadUrl("personal_annual_report_long.png", pngUrl);
    setStatus({
      en: "Long PNG exported from the current annual report.",
      zh: "已导出当前年报完整长图。",
    });
  } catch (error) {
    console.warn("DOM PNG export failed, falling back to summary canvas.", error);
    exportSummaryPng();
    setStatus({
      en: "Long PNG fallback exported. Some browser styles may be simplified.",
      zh: "已用兜底方式导出长图，部分样式可能简化。",
    });
  }
}

async function renderReportElementToPng() {
  const width = 430;
  const scale = 2;
  const stage = document.createElement("div");
  stage.className = "png-export-stage";
  stage.style.position = "fixed";
  stage.style.left = "-10000px";
  stage.style.top = "0";
  stage.style.width = `${width}px`;
  stage.style.background = "#ede7dc";
  const clone = report.cloneNode(true);
  clone.style.width = `${width}px`;
  stage.appendChild(clone);
  document.body.appendChild(stage);
  await nextFrame();
  const height = Math.ceil(stage.scrollHeight);
  const serialized = stage.innerHTML;
  const css = getEmbeddedStyles() || getReportExportCss();
  document.body.removeChild(stage);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <foreignObject width="100%" height="100%">
        <div xmlns="http://www.w3.org/1999/xhtml" class="png-export-root" style="width:${width}px;background:#ede7dc;">
          <style>${css}</style>
          ${serialized}
        </div>
      </foreignObject>
    </svg>`;
  const image = await loadImage(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
  const canvas = document.createElement("canvas");
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ede7dc";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}

function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
}

function exportSummaryPng() {
  const canvas = document.createElement("canvas");
  const width = 1080;
  const padding = 68;
  const lines = shareImageLines();
  const lineHeight = 42;
  const height = Math.max(1600, 280 + lines.length * lineHeight + padding * 2);
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#f7f3ec";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#1f2328";
  ctx.fillRect(36, 36, width - 72, height - 72);
  ctx.fillStyle = "#fffaf1";
  ctx.fillRect(62, 62, width - 124, height - 124);
  let y = 150;
  ctx.fillStyle = "#a83d35";
  ctx.font = "800 30px system-ui";
  ctx.fillText(state.lang === "zh" ? "本地个人年报" : "Local Annual Report", padding, y);
  y += 96;
  ctx.fillStyle = "#1f2328";
  ctx.font = "950 88px system-ui";
  y = drawWrappedText(ctx, state.narrative[state.lang].title, padding, y, width - padding * 2, 92);
  y += 36;
  ctx.font = "800 42px system-ui";
  y = drawWrappedText(ctx, state.narrative[state.lang].persona, padding, y, width - padding * 2, 52);
  y += 38;
  ctx.font = "500 34px system-ui";
  for (const line of lines) {
    y = drawWrappedText(ctx, line, padding, y, width - padding * 2, lineHeight);
    y += 16;
  }
  downloadUrl("personal_annual_report_share.png", canvas.toDataURL("image/png"));
}

function shareImageLines() {
  const metrics = state.metrics;
  const copy = state.narrative[state.lang];
  if (state.lang === "zh") {
    return [
      copy.verdict,
      `净消费：${moneyText(metrics.netConsumption)}｜已排除还款：${moneyText(metrics.repaymentTotal)}`,
      `退款挽回：${moneyText(metrics.refundDeduction)}｜投资及中性流：${moneyText(metrics.investmentTotal + metrics.neutralTotal)}`,
      copy.segment,
      copy.quote,
      "本地生成，无上传、无登录、无 API。",
    ];
  }
  return [
    copy.verdict,
    `Net consumption: ${moneyText(metrics.netConsumption)} | Repayments excluded: ${moneyText(metrics.repaymentTotal)}`,
    `Refund recovery: ${moneyText(metrics.refundDeduction)} | Investment flow: ${moneyText(metrics.investmentTotal)}`,
    copy.segment,
    copy.quote,
    "Generated locally. No upload, no login, no API.",
  ];
}

function groupByAmount(rows, labelFn) {
  return rows.reduce((acc, row) => {
    const label = labelFn(row) || "unknown";
    acc[label] = (acc[label] || 0) + numeric(row.amount);
    return acc;
  }, {});
}

function displayCategory(value) {
  const label = String(value || "").trim();
  const map = {
    merchant_payment: "普通消费",
    platform_reward: "平台奖励",
    refund_in: "退款",
    credit_repayment: "信用还款",
    personal_repayment: "还款",
    internal_transfer: "内部转账",
    investment_flow: "投资理财",
    neutral_flow: "不计收支",
    uncategorized: "未分类消费",
  };
  return map[label] || label || "未分类消费";
}

function topEntries(group, limit) {
  return Object.entries(group)
    .map(([label, value]) => ({ label, value }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);
}

function inferDateRange(rows) {
  const dates = rows.map((row) => row.transaction_time.slice(0, 10)).filter(Boolean).sort();
  if (!dates.length) return "unknown period";
  return dates[0] === dates[dates.length - 1] ? dates[0] : `${dates[0]} to ${dates[dates.length - 1]}`;
}

function pickByHash(items, seed) {
  if (!items.length) return "";
  return items[Math.abs(seed) % items.length];
}

function numeric(value) {
  const cleaned = String(value ?? "0").replace(/,/g, "").trim();
  const parsed = Number(cleaned || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function sum(rows, field) {
  return rows.reduce((total, row) => total + numeric(row[field]), 0);
}

function moneyText(value) {
  return numeric(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function percentText(value, total) {
  const denominator = numeric(total);
  if (!denominator) return "0.0%";
  return `${((numeric(value) / denominator) * 100).toFixed(1)}%`;
}

function applyStaticLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    if (staticCopy[key]) node.textContent = staticCopy[key][state.lang];
  });
}

function setStatus(message) {
  currentStatus = message;
  updateStatus();
}

function updateStatus() {
  statusBox.textContent = currentStatus[state.lang];
}

function t(en, zh) {
  return state.lang === "zh" ? zh : en;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[char]));
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  downloadUrl(filename, URL.createObjectURL(blob));
}

function downloadUrl(filename, url) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  if (url.startsWith("blob:")) {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

function getEmbeddedStyles() {
  return Array.from(document.styleSheets).map((sheet) => {
    try {
      return Array.from(sheet.cssRules || []).map((rule) => rule.cssText).join("\n");
    } catch {
      return "";
    }
  }).join("\n");
}

function getReportExportCss() {
  return `
    * { box-sizing: border-box; }
    .png-export-root {
      margin: 0;
      color: #1f2328;
      background: #ede7dc;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .png-export-root h1,
    .png-export-root h2,
    .png-export-root h3,
    .png-export-root p { margin-top: 0; }
    .png-export-root .report { width: 430px; }
    .png-export-root .annual-stack { display: grid; gap: 0; }
    .png-export-root .report-card {
      overflow: hidden;
      padding: 22px;
      border: 1px solid #e4dacd;
      border-width: 0 0 1px;
      background: #fffaf1;
    }
    .png-export-root .cover-card {
      min-height: 560px;
      color: #fff;
      background:
        linear-gradient(155deg, rgba(31, 35, 40, 0.92), rgba(31, 35, 40, 0.62)),
        linear-gradient(45deg, #203a43, #a83d35 52%, #d4a23a);
    }
    .png-export-root .eyebrow,
    .png-export-root .card-kicker {
      margin: 0 0 8px;
      color: #a83d35;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    .png-export-root .cover-card .eyebrow,
    .png-export-root .cover-card .privacy-line {
      color: rgba(255, 255, 255, 0.78);
    }
    .png-export-root .cover-title {
      margin: 70px 0 20px;
      color: #fff;
      font-size: 58px;
      font-weight: 950;
      line-height: 0.96;
      letter-spacing: 0;
    }
    .png-export-root .cover-verdict {
      margin: 0;
      color: #fff;
      font-size: 23px;
      font-weight: 900;
      line-height: 1.28;
    }
    .png-export-root .privacy-line {
      margin-top: 72px;
      padding-top: 16px;
      border-top: 1px solid rgba(255, 255, 255, 0.24);
      font-size: 13px;
      line-height: 1.5;
    }
    .png-export-root .card-title {
      margin-bottom: 12px;
      font-size: 28px;
      font-weight: 900;
      line-height: 1.05;
    }
    .png-export-root .segment-summary {
      display: grid;
      gap: 8px;
      margin-bottom: 18px;
    }
    .png-export-root .segment-title {
      margin-bottom: 0;
      font-size: 26px;
      font-weight: 900;
      line-height: 1.08;
    }
    .png-export-root .segment-hero {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 14px;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(31, 35, 40, 0.12);
    }
    .png-export-root .segment-hero span {
      font-size: 32px;
      font-weight: 950;
      line-height: 1.05;
    }
    .png-export-root .segment-hero strong {
      font-size: 22px;
      font-variant-numeric: tabular-nums;
    }
    .png-export-root .segment-meta {
      margin: 0;
      color: #6b7280;
      font-size: 15px;
      font-weight: 800;
    }
    .png-export-root .discussion-title {
      margin-bottom: 0;
      max-width: 11em;
      font-size: 28px;
      font-weight: 900;
      line-height: 1.12;
    }
    .png-export-root .big-number {
      margin: 16px 0 8px;
      font-size: 44px;
      font-weight: 950;
      line-height: 1;
    }
    .png-export-root .muted {
      color: #6b7280;
      line-height: 1.5;
    }
    .png-export-root .roast {
      margin: 14px 0 0;
      font-size: 18px;
      font-weight: 850;
      line-height: 1.42;
    }
    .png-export-root .secondary-roast {
      color: #3b3f46;
      font-size: 16px;
      font-weight: 750;
    }
    .png-export-root .mini-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .png-export-root .mini-metric {
      min-height: 118px;
      padding: 14px;
      border: 1px solid rgba(31, 35, 40, 0.12);
      border-radius: 8px;
      background: #fffdf8;
    }
    .png-export-root .mini-metric span {
      display: block;
      color: #6b7280;
      font-size: 12px;
      line-height: 1.35;
    }
    .png-export-root .mini-metric strong {
      display: block;
      margin: 10px 0 6px;
      font-size: 24px;
      line-height: 1;
    }
    .png-export-root .statement {
      display: grid;
      gap: 10px;
      margin: 18px 0 0;
    }
    .png-export-root .statement-row {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(31, 35, 40, 0.12);
      font-size: 15px;
    }
    .png-export-root .statement-row strong,
    .png-export-root .bar-top span:last-child {
      font-variant-numeric: tabular-nums;
    }
    .png-export-root .bar-list {
      display: grid;
      gap: 12px;
      margin-top: 16px;
    }
    .png-export-root .compact-bars {
      gap: 14px;
      margin-top: 0;
    }
    .png-export-root .bar-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: 14px;
      font-weight: 800;
    }
    .png-export-root .bar-top span:first-child,
    .png-export-root .bar-top span:last-child {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }
    .png-export-root .bar-top b {
      color: #25766b;
      font-size: 12px;
    }
    .png-export-root .bar-top small {
      color: #6b7280;
      font-size: 11px;
      font-weight: 800;
    }
    .png-export-root .bar {
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(31, 35, 40, 0.1);
    }
    .png-export-root .bar span {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, #25766b, #d4a23a);
    }
    .png-export-root .risk-list,
    .png-export-root .question-list {
      display: grid;
      gap: 10px;
      padding: 0;
      margin: 14px 0 0;
      list-style: none;
    }
    .png-export-root .risk-list li,
    .png-export-root .question-list li {
      padding: 12px;
      border-left: 4px solid #a83d35;
      background: #fffdf8;
      border-radius: 4px;
      line-height: 1.45;
    }
    .png-export-root .question-list { counter-reset: question; }
    .png-export-root .question-list li {
      display: grid;
      grid-template-columns: 28px 1fr;
      gap: 10px;
      align-items: start;
      border-left-color: #25766b;
      font-weight: 760;
    }
    .png-export-root .question-list li::before {
      counter-increment: question;
      content: counter(question);
      display: grid;
      width: 24px;
      height: 24px;
      place-items: center;
      border-radius: 999px;
      background: #25766b;
      color: #fff;
      font-size: 12px;
      font-weight: 900;
    }
    .png-export-root .quote-mark {
      color: #a83d35;
      font-size: 42px;
      font-weight: 950;
      line-height: 1;
    }
    .png-export-root .share-card {
      background: #1f2328;
      color: #fff;
    }
    .png-export-root .share-card .card-kicker,
    .png-export-root .share-card .muted {
      color: rgba(255, 255, 255, 0.72);
    }
  `;
}

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight) {
  const chars = Array.from(String(text));
  let line = "";
  for (const char of chars) {
    const test = line + char;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      line = char;
      y += lineHeight;
    } else {
      line = test;
    }
  }
  if (line) {
    ctx.fillText(line, x, y);
    y += lineHeight;
  }
  return y;
}
