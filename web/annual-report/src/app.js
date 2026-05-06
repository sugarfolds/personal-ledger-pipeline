const state = {
  lang: "en",
  style: "board_roast",
  rows: [],
  metrics: null,
};

const report = document.querySelector("#report");
const statusBox = document.querySelector("#status");
const fileInput = document.querySelector("#fileInput");
const styleSelect = document.querySelector("#styleSelect");

document.documentElement.dataset.activeLang = state.lang;

document.querySelectorAll("[data-lang]").forEach((button) => {
  button.addEventListener("click", () => {
    state.lang = button.dataset.lang;
    document.documentElement.dataset.activeLang = state.lang;
    document.querySelectorAll("[data-lang]").forEach((item) => item.classList.toggle("active", item === button));
    render();
  });
});

styleSelect.addEventListener("change", () => {
  state.style = styleSelect.value;
  render();
});

fileInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const rows = file.name.toLowerCase().endsWith(".json") ? parseJson(text) : parseCsv(text);
    state.rows = cleanRows(normalizeRows(rows));
    state.metrics = computeMetrics(state.rows);
    setStatus(`Loaded ${state.rows.length} rows from ${file.name}.`, `已载入 ${state.rows.length} 行：${file.name}。`);
    render();
  } catch (error) {
    console.error(error);
    setStatus(`Could not parse this file: ${error.message}`, `文件解析失败：${error.message}`);
  }
});

document.querySelector("#exportMarkdown").addEventListener("click", () => {
  if (!state.metrics) return;
  download("personal_annual_report.md", markdownReport(), "text/markdown");
});

document.querySelector("#exportHtml").addEventListener("click", () => {
  if (!state.metrics) return;
  const html = `<!doctype html><meta charset="utf-8"><title>Personal Annual Report</title><style>${getEmbeddedStyles()}</style>${report.outerHTML}`;
  download("personal_annual_report.html", html, "text/html");
});

document.querySelector("#exportPng").addEventListener("click", () => {
  if (!state.metrics) return;
  const canvas = document.createElement("canvas");
  canvas.width = 1200;
  canvas.height = 1600;
  const ctx = canvas.getContext("2d");
  const m = state.metrics;
  ctx.fillStyle = "#fbfaf7";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#202124";
  ctx.font = "700 72px system-ui";
  wrapText(ctx, t("Personal Annual Report", "个人年报"), 80, 150, 1040, 86);
  ctx.fillStyle = "#1f766f";
  ctx.font = "700 42px system-ui";
  ctx.fillText(t(m.persona.en, m.persona.zh), 80, 330);
  ctx.fillStyle = "#202124";
  ctx.font = "500 34px system-ui";
  [
    [t("Net consumption", "净消费"), formatMoney(m.netConsumption)],
    [t("Gross income", "总收入"), formatMoney(m.grossIncome)],
    [t("Refund deduction", "退款抵扣"), formatMoney(m.refundDeduction)],
    [t("Review rows", "复核行数"), String(m.reviewRows)],
  ].forEach(([label, value], index) => {
    const y = 460 + index * 130;
    ctx.fillStyle = "#68707d";
    ctx.fillText(label, 80, y);
    ctx.fillStyle = "#202124";
    ctx.font = "700 46px system-ui";
    ctx.fillText(value, 80, y + 58);
    ctx.font = "500 34px system-ui";
  });
  ctx.fillStyle = "#ad3d31";
  ctx.font = "700 32px system-ui";
  wrapText(ctx, t(copy().verdict.en, copy().verdict.zh), 80, 1120, 1040, 42);
  downloadUrl("personal_annual_report.png", canvas.toDataURL("image/png"));
});

function parseJson(text) {
  const data = JSON.parse(text);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.rows)) return data.rows;
  throw new Error("JSON must be an array or { rows: [...] }.");
}

function parseCsv(text) {
  const rows = [];
  const lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").filter(Boolean);
  if (!lines.length) return rows;
  const headers = splitCsvLine(lines[0]).map((header) => header.trim());
  for (const line of lines.slice(1)) {
    const values = splitCsvLine(line);
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    rows.push(row);
  }
  return rows;
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

function normalizeRows(rows) {
  return rows.map((row, index) => {
    const text = `${row.counterparty || ""} ${row.item_title || row.description || ""} ${row.payment_method || ""} ${row.kind || ""}`;
    const flow = row.direction || row.raw_direction || row.income_expense || "";
    const amount = numeric(row.amount || row.debit || row.credit || 0);
    const normalizedType = row.normalized_type || inferType(text, flow, row);
    return {
      source: row.source || inferSource(row.source_file || ""),
      source_file: row.source_file || "browser_upload",
      raw_row_number: row.raw_row_number || String(index + 1),
      transaction_time: row.transaction_time || row.time || row.date || "",
      direction: row.direction || inferDirection(flow, row, normalizedType),
      amount,
      counterparty: row.counterparty || "",
      item_title: row.item_title || row.description || "",
      payment_method: row.payment_method || "",
      transaction_id: row.transaction_id || row.id || "",
      related_transaction_id: row.related_transaction_id || "",
      normalized_type: normalizedType,
      normalized_status: row.normalized_status || (normalizedType === "refund_in" ? "refund" : "success"),
      account_platform: row.account_platform || row.source || "",
      account_name: row.account_name || row.payment_method || "",
      transfer_scope: row.transfer_scope || "external",
      include_in_ledger: row.include_in_ledger || "true",
      needs_review: row.needs_review || "false",
      clean_status: row.clean_status || "active",
      clean_rule: row.clean_rule || "",
    };
  });
}

function inferType(text, flow, row) {
  const lower = text.toLowerCase();
  if (lower.includes("repayment") || text.includes("还款")) return "credit_repayment";
  if (lower.includes("top-up") || lower.includes("topup") || text.includes("充值") || text.includes("转账")) return "internal_transfer";
  if (lower.includes("refund") || text.includes("退款") || flow === "收入" && row.related_transaction_id) return "refund_in";
  if (lower.includes("reward") || lower.includes("campaign") || text.includes("奖励") || text.includes("补贴")) return "platform_reward";
  if (row.credit && !row.debit) return "bank_income";
  if (row.debit && !row.credit) return "bank_payment";
  if (flow === "其他") return "unknown_wallet_flow";
  return "merchant_payment";
}

function inferDirection(flow, row, normalizedType) {
  if (normalizedType === "unknown_wallet_flow") return "neutral";
  if (normalizedType === "refund_in" || normalizedType === "platform_reward" || row.credit || flow === "收入") return "income";
  return "expense";
}

function inferSource(sourceFile) {
  const value = sourceFile.toLowerCase();
  return ["alipay", "wechat", "meituan", "douyin", "boc", "cmb", "icbc", "abc"].find((source) => value.includes(source)) || "upload";
}

function cleanRows(rows) {
  const appExpenses = rows.filter((row) => ["alipay", "wechat", "douyin", "meituan"].includes(row.source) && row.direction === "expense" && row.normalized_type === "merchant_payment");
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
    } else if (next.normalized_type === "unknown_wallet_flow") {
      next.transfer_scope = "unknown";
      next.include_in_ledger = "false";
      next.needs_review = "true";
      next.clean_status = "needs_review";
      next.clean_rule = "ambiguous_wallet_flow";
    }
    if (["boc", "cmb", "icbc", "abc"].includes(next.source) && next.normalized_type === "bank_payment") {
      const bankTime = Date.parse(next.transaction_time);
      const duplicate = appExpenses.some((appRow) => numeric(appRow.amount) === numeric(next.amount) && Math.abs(bankTime - Date.parse(appRow.transaction_time)) <= 120000);
      if (duplicate) {
        next.include_in_ledger = "false";
        next.clean_status = "excluded_duplicate_payment";
        next.clean_rule = "bank_charge_shadowed_by_app_detail";
      }
    }
    return next;
  });
}

function computeMetrics(rows) {
  const refunds = new Map();
  rows.forEach((row) => {
    if (row.normalized_type === "refund_in" && row.related_transaction_id) {
      refunds.set(row.related_transaction_id, (refunds.get(row.related_transaction_id) || 0) + numeric(row.amount));
    }
  });
  const included = rows.filter((row) => row.include_in_ledger === "true");
  const expenses = included.filter((row) => row.direction === "expense");
  const income = included.filter((row) => row.direction === "income" && row.normalized_type !== "refund_in");
  const grossIncome = sum(income, "amount");
  const grossExpense = sum(expenses, "amount");
  const refundDeduction = expenses.reduce((total, row) => total + (refunds.get(row.transaction_id) || 0), 0);
  const netConsumption = grossExpense - refundDeduction;
  const bySource = {};
  expenses.forEach((row) => {
    bySource[row.source] = (bySource[row.source] || 0) + numeric(row.amount) - (refunds.get(row.transaction_id) || 0);
  });
  const reviewRows = rows.filter((row) => row.needs_review === "true" || row.clean_status === "needs_review").length;
  const repaymentTotal = sum(rows.filter((row) => row.transfer_scope === "debt_repayment"), "amount");
  const internalTransferTotal = sum(rows.filter((row) => row.transfer_scope === "internal"), "amount");
  const duplicateTotal = sum(rows.filter((row) => row.clean_status === "excluded_duplicate_payment"), "amount");
  const topSource = Object.entries(bySource).sort((a, b) => b[1] - a[1])[0] || ["n/a", 0];
  const persona = choosePersona({ netConsumption, repaymentTotal, reviewRows, topSource });
  return {
    rows: rows.length,
    included: included.length,
    grossIncome,
    grossExpense,
    refundDeduction,
    netConsumption,
    netCashflow: grossIncome - grossExpense,
    reviewRows,
    repaymentTotal,
    internalTransferTotal,
    duplicateTotal,
    topSource,
    bySource,
    persona,
  };
}

function choosePersona(metrics) {
  if (metrics.netConsumption === 0) return { en: "Zero-Spend CFO", zh: "零支出 CFO" };
  if (metrics.repaymentTotal > metrics.netConsumption / 2) return { en: "Debt-Service Maximalist", zh: "还款优先型 CFO" };
  if (metrics.reviewRows > 0) return { en: "Audit-Committee Frequent Flyer", zh: "审计委员会常驻嘉宾" };
  if (metrics.topSource[1] > metrics.netConsumption / 2) return { en: "Single-Segment Enthusiast", zh: "单一分部信仰者" };
  return { en: "Diversified Small-Cap Household", zh: "分散型小市值家庭公司" };
}

function copy() {
  const serious = {
    letter: {
      en: "Management reports a traceable period. Income, consumption, refunds, repayment timing, and review items were separated before the narrative received permission to sound confident.",
      zh: "管理层提交了一段可追溯账期。收入、消费、退款、还款时点和复核事项先拆清楚，叙事层再开始发言。",
    },
    verdict: {
      en: "The board finds the entity traceable and solvent in this ledger view. Further confidence requires balance snapshots, review decisions, and fewer purchases pretending to be strategy.",
      zh: "董事会认为，本账本视角下主体具备可追溯性和偿付能力。后续信心需要余额快照、复核结论，以及少一点把消费包装成战略的冲动。",
    },
  };
  const boardRoast = {
    letter: {
      en: "Management congratulates itself on classification discipline. The board notes that labeling a purchase carefully does not make it strategic.",
      zh: "管理层对分类能力表示满意。董事会提醒：一笔消费被命名得很专业，账单金额也不会自动降低。",
    },
    verdict: {
      en: "The finance function has improved. The strategy function is invited to stop calling every purchase an investment.",
      zh: "财务职能有进步。战略职能请停止把每一笔消费都称为长期投入。",
    },
  };
  const social = {
    letter: {
      en: "My year in money: classified, reconciled, lightly roasted.",
      zh: "我的年度金钱切片：已分类、已对账、已接受轻度锐评。",
    },
    verdict: {
      en: "A shareable report card for spending habits, generated locally.",
      zh: "一张可分享的消费习惯成绩单，在本地生成。",
    },
  };
  return { serious, board_roast: boardRoast, social_share: social }[state.style];
}

function render() {
  if (!state.metrics) return;
  const m = state.metrics;
  const entries = Object.entries(m.bySource).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, value]) => value), 1);
  report.innerHTML = `
    <header class="report-header">
      <div>
        <p class="eyebrow">${t("Local Annual Report", "本地个人年报")}</p>
        <h2 class="report-title">${t("Personal Annual Report", "个人年度报告")}</h2>
        <p>${escapeHtml(copy().letter[state.lang])}</p>
      </div>
      <aside class="verdict">
        <strong>${t(m.persona.en, m.persona.zh)}</strong>
        <p>${escapeHtml(copy().verdict[state.lang])}</p>
      </aside>
    </header>
    <section class="metrics">
      ${metric(t("Net consumption", "净消费"), formatMoney(m.netConsumption), t("After matched refund deductions", "已扣除匹配退款"))}
      ${metric(t("Gross income", "总收入"), formatMoney(m.grossIncome), t("Refunds excluded from income", "退款未计入普通收入"))}
      ${metric(t("Repayments excluded", "已排除还款"), formatMoney(m.repaymentTotal), t("Shown as timing, not new spend", "作为还款时点展示"))}
      ${metric(t("Manual review", "人工复核"), String(m.reviewRows), t("Second-pass governance queue", "二道复核工序"))}
    </section>
    <section class="section-grid">
      <div class="block">
        <h3>${t("Income Statement", "个人利润表")}</h3>
        <table class="data-table">
          ${tableRow(t("Income", "收入"), formatMoney(m.grossIncome))}
          ${tableRow(t("Gross expense", "退款前总支出"), formatMoney(m.grossExpense))}
          ${tableRow(t("Refund deduction", "退款抵扣"), formatMoney(m.refundDeduction))}
          ${tableRow(t("Net consumption", "净消费"), formatMoney(m.netConsumption))}
          ${tableRow(t("Net cashflow view", "账本视角净现金流"), formatMoney(m.netCashflow))}
        </table>
      </div>
      <div class="block">
        <h3>${t("Segment Performance", "分部表现")}</h3>
        <div class="bars">
          ${entries.map(([source, value]) => `<div><div class="bar-top"><strong>${escapeHtml(source)}</strong><span>${formatMoney(value)}</span></div><div class="bar"><span style="width:${Math.max(4, value / max * 100)}%"></span></div></div>`).join("") || `<p>${t("No included consumption segment.", "暂无纳入消费口径的分部。")}</p>`}
        </div>
      </div>
      <div class="block">
        <h3>${t("Risk Factors", "风险因素")}</h3>
        <ul>
          <li>${t("Repayment rows can inflate spending if counted twice.", "还款行若重复计入，会夸大真实消费。")}</li>
          <li>${t("Internal transfers need account-flow treatment.", "内部转账需要走账户流动口径。")}</li>
          <li>${t("Douyin-style platform bills mix refunds, rewards, merchant payments, and repayment labels.", "抖音类平台账单会混合退款、奖励、商户消费与还款标签。")}</li>
          <li>${t("Manual review remains the second pass for ambiguous rows.", "人工复核保留为模糊行的二道工序。")}</li>
        </ul>
      </div>
      <div class="block">
        <h3>${t("Auditor Notes", "审计说明")}</h3>
        <ul class="pill-list">
          <li>${t("Cleaned rows only", "仅使用 cleaned rows")}</li>
          <li>${t("No invented balances", "不编造余额")}</li>
          <li>${t("Local browser processing", "浏览器本地处理")}</li>
          <li>${t("No API call", "无 API 调用")}</li>
        </ul>
      </div>
    </section>
  `;
}

function metric(label, value, note) {
  return `<article class="metric"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`;
}

function tableRow(label, value) {
  return `<tr><th>${label}</th><td>${value}</td></tr>`;
}

function markdownReport() {
  const m = state.metrics;
  return [
    `# ${t("Personal Annual Report", "个人年度报告")}`,
    "",
    copy().letter[state.lang],
    "",
    `- ${t("Net consumption", "净消费")}: ${formatMoney(m.netConsumption)}`,
    `- ${t("Gross income", "总收入")}: ${formatMoney(m.grossIncome)}`,
    `- ${t("Refund deduction", "退款抵扣")}: ${formatMoney(m.refundDeduction)}`,
    `- ${t("Repayments excluded", "已排除还款")}: ${formatMoney(m.repaymentTotal)}`,
    `- ${t("Manual review rows", "人工复核行")}: ${m.reviewRows}`,
    "",
    `## ${t("Board Verdict", "董事会结论")}`,
    "",
    copy().verdict[state.lang],
    "",
  ].join("\n");
}

function numeric(value) {
  const cleaned = String(value ?? "0").replace(/,/g, "").trim();
  const parsed = Number(cleaned || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function sum(rows, field) {
  return rows.reduce((total, row) => total + numeric(row[field]), 0);
}

function formatMoney(value) {
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function setStatus(en, zh) {
  statusBox.innerHTML = `<span class="lang lang-en">${escapeHtml(en)}</span><span class="lang lang-zh">${escapeHtml(zh)}</span>`;
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
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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

function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = text.split(/\s+/);
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth) {
      ctx.fillText(line, x, y);
      line = word;
      y += lineHeight;
    } else {
      line = test;
    }
  }
  ctx.fillText(line, x, y);
}
