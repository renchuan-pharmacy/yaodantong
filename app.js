"use strict";

const CATALOG_URL = "data/public_catalog.json";
const PAGE_SIZE = 20;
let catalog = [];
let matches = [];
let visibleCount = PAGE_SIZE;
let searchTimer;

const form = document.querySelector("#search-form");
const input = document.querySelector("#search-input");
const results = document.querySelector("#results");
const message = document.querySelector("#message");
const showMore = document.querySelector("#show-more");
const status = document.querySelector("#catalog-status");
const sourceMeta = document.querySelector("#source-meta");

function normalize(value) {
  return String(value || "").normalize("NFKC").toLocaleLowerCase("zh-TW").trim();
}

function createText(tag, className, value) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = value || "—";
  return element;
}

function detail(term, description) {
  const wrapper = document.createElement("div");
  wrapper.append(createText("dt", "", term), createText("dd", "", description));
  return wrapper;
}

function makeLink(label, href) {
  const link = document.createElement("a");
  link.textContent = label;
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function renderCard(drug) {
  const card = document.createElement("article");
  card.className = "drug-card";

  const top = document.createElement("div");
  top.className = "drug-top";
  const names = document.createElement("div");
  names.append(createText("h3", "", drug.nameZh || drug.nameEn));
  names.append(createText("p", "drug-en", drug.nameEn));
  top.append(names, createText("span", "drug-code", drug.code));

  const details = document.createElement("dl");
  details.className = "drug-details";
  details.append(
    detail("成分", drug.ingredient),
    detail("劑型", drug.dosageForm),
    detail("規格", drug.spec),
    detail("製造廠／藥商", drug.manufacturer)
  );

  const note = createText(
    "p",
    "card-note",
    drug.currentlyCovered
      ? "健保資料顯示為目前有效品項；本頁不代表店內現貨。"
      : "這是歷史品項，給付狀態可能已變更；請以健保署最新查詢及藥師確認為準。"
  );

  const links = document.createElement("div");
  links.className = "drug-links";
  if (drug.licenseUrl && drug.licenseUrl.startsWith("https://")) {
    links.append(makeLink("查看食藥署許可證／仿單", drug.licenseUrl));
  }
  links.append(makeLink("LINE 詢問是否有現貨", "https://line.me/R/ti/p/%40179ewiti"));

  card.append(top, details, note, links);
  return card;
}

function render() {
  results.replaceChildren();
  const visible = matches.slice(0, visibleCount);
  visible.forEach((drug) => results.append(renderCard(drug)));
  showMore.hidden = visibleCount >= matches.length;

  if (matches.length) {
    message.className = "message";
    message.textContent = `找到 ${matches.length.toLocaleString("zh-TW")} 筆，已顯示 ${visible.length.toLocaleString("zh-TW")} 筆。`;
  }
}

function search(query) {
  const q = normalize(query);
  visibleCount = PAGE_SIZE;
  results.replaceChildren();
  showMore.hidden = true;

  if (!q) {
    matches = [];
    message.className = "message";
    message.textContent = "請先輸入藥名、成分或健保碼。";
    return;
  }

  matches = catalog.filter((drug) => [
    drug.code, drug.nameZh, drug.nameEn, drug.ingredient, drug.dosageForm,
    drug.manufacturer, drug.atcCode
  ].some((value) => normalize(value).includes(q)));

  if (!matches.length) {
    message.className = "message";
    message.textContent = "查不到相符品項。請確認拼字，或用 LINE 請小彌藥師協助核對。";
    return;
  }
  render();
}

async function loadCatalog() {
  try {
    const response = await fetch(CATALOG_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    catalog = Array.isArray(data.items) ? data.items : [];
    status.textContent = `${catalog.length.toLocaleString("zh-TW")} 項可查`;
    const updated = new Date(data.generatedAt);
    sourceMeta.textContent = `公開目錄更新：${updated.toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}。店內 Excel 僅用於篩選藥碼，未公開即時庫存或內部編號。`;

    const initialQuery = new URLSearchParams(location.search).get("q") || "";
    if (initialQuery) {
      input.value = initialQuery;
      search(initialQuery);
    }
  } catch (error) {
    status.textContent = "載入失敗";
    message.className = "message error";
    message.textContent = "目前無法載入藥品資料，請稍後重新整理，或直接詢問藥師。";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = input.value.trim();
  const url = new URL(location.href);
  if (query) url.searchParams.set("q", query);
  else url.searchParams.delete("q");
  history.replaceState({}, "", url);
  search(query);
});

input.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const query = input.value.trim();
    if (!query || normalize(query).length >= 2) search(query);
  }, 250);
});

showMore.addEventListener("click", () => {
  visibleCount += PAGE_SIZE;
  render();
});

loadCatalog();
