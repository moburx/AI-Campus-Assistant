// ========================================
// AI Campus Assistant - 학교 공지 (сургуулийн мэдэгдэл)
// ========================================
// Сервер сургуулийн самбараас татсан мэдэгдлүүдийг харуулна.
// Шинэчлэх товч нь серверт 10 минутад нэг удаа л зөвшөөрөгдөнө.

const NOTICE_NEW_DAYS = 3;          // сүүлийн 3 хоногийн мэдэгдэлд "NEW" тэмдэг
const NOTICE_AUTO_REFRESH_HOURS = 6; // үүнээс хуучин бол нэвтрэхэд автоматаар шинэчилнэ
const NOTICE_VISIBLE_COUNT = 8;      // эхэндээ харуулах тоо ("Дэлгэрэнгүй" дарвал бүгд)
const NOTICE_LOAD_LIMIT = 150;       // серверээс авах дээд тоо (3 самбар × 3 хуудас ≈ 90)
const NOTICE_SCOPE_KEY = "campus_notice_scope";

let schoolNotices = [];
let noticesLastRefreshed = null;
let showAllNotices = false;
let noticeScope = loadNoticeScope(); // "international" | "academic" | "all"

// AI тайлбар: "мэдэгдлийн id:хэл" → текст. Нээлттэй байгаа мэдэгдлүүдийн id.
const noticeSummaries = {};
const openSummaries = new Set();
const loadingSummaries = new Set();

const noticeList = document.getElementById("notice-list");
const noticeStatus = document.getElementById("notices-status");
const noticeRefreshButton = document.getElementById("notices-refresh");
const noticeMoreButton = document.getElementById("notices-more");
const noticeScopeButtons = document.querySelectorAll("[data-notice-scope]");

function loadNoticeScope() {
    try {
        const saved = localStorage.getItem(NOTICE_SCOPE_KEY);
        return ["academic", "all"].includes(saved) ? saved : "international";
    } catch (error) {
        return "international";
    }
}

// Бүгдийг нэг удаа татаад, сонгосон хүрээгээр (scope) нь браузер дээр шүүнэ.
async function loadNotices() {
    const data = await apiJson(`/notices?limit=${NOTICE_LOAD_LIMIT}&scope=all`, {}, "notices.failed");
    schoolNotices = data.notices;
    noticesLastRefreshed = data.last_refreshed;
}

function internationalNotices() {
    return schoolNotices.filter(notice => notice.international !== false);
}

function academicNotices() {
    return schoolNotices.filter(notice => notice.category === "academic");
}

function scopedNotices() {
    if (noticeScope === "all") return schoolNotices;
    if (noticeScope === "academic") return academicNotices();
    return internationalNotices();
}

function renderNoticeScope() {
    const counts = {
        international: internationalNotices().length,
        academic: academicNotices().length,
        all: schoolNotices.length
    };
    const labels = {
        international: "notices.scopeInternational",
        academic: "notices.scopeAcademic",
        all: "notices.scopeAll"
    };

    noticeScopeButtons.forEach(button => {
        const scope = button.dataset.noticeScope;
        button.setAttribute("aria-pressed", String(scope === noticeScope));
        button.textContent = `${t(labels[scope])} ${counts[scope]}`;
    });
}

noticeScopeButtons.forEach(button => {
    button.addEventListener("click", () => {
        noticeScope = button.dataset.noticeScope;
        showAllNotices = false;
        try {
            localStorage.setItem(NOTICE_SCOPE_KEY, noticeScope);
        } catch (error) {
            // localStorage ашиглах боломжгүй орчин
        }
        renderNotices();
    });
});

function resetNotices() {
    schoolNotices = [];
    noticesLastRefreshed = null;
    showAllNotices = false;
    openSummaries.clear();
    Object.keys(noticeSummaries).forEach(key => delete noticeSummaries[key]);
    noticeStatus.textContent = "";
}

function hoursSince(isoTime) {
    if (!isoTime) return Infinity;
    return (Date.now() - new Date(isoTime).getTime()) / (1000 * 60 * 60);
}

function formatRefreshTime(isoTime) {
    if (!isoTime) return t("notices.never");

    const date = new Date(isoTime);
    const day = formatDateObject(date, { month: "short", day: "numeric" });
    const time = date.toLocaleTimeString(getLocale(), { hour: "2-digit", minute: "2-digit" });
    return t("notices.lastUpdated", { time: `${day} ${time}` });
}

function createNoticeItem(notice) {
    const item = document.createElement("li");
    item.className = "notice-item";

    const meta = document.createElement("div");
    meta.className = "notice-meta";

    const date = document.createElement("span");
    date.textContent = formatDate(notice.posted_at);

    const source = document.createElement("span");
    source.className = "notice-source";
    source.textContent = notice.source;

    meta.append(date, source);

    if (notice.pinned) {
        const pinned = document.createElement("span");
        pinned.className = "notice-badge notice-pinned";
        pinned.textContent = `📌 ${t("notices.pinned")}`;
        meta.appendChild(pinned);
    }

    if (-daysUntil(notice.posted_at) <= NOTICE_NEW_DAYS) {
        const fresh = document.createElement("span");
        fresh.className = "notice-badge notice-new";
        fresh.textContent = t("notices.new");
        meta.appendChild(fresh);
    }

    // Гарчиг нь сургуулийн анхны нийтлэл рүү шинэ цонхоор нээгдэнэ.
    const link = document.createElement("a");
    link.className = "notice-title";
    link.href = notice.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = notice.title;
    link.title = t("notices.openOriginal");

    item.append(meta, link, createSummaryArea(notice));
    return item;
}

// ---------- AI тайлбар ----------
function summaryKey(noticeId) {
    return `${noticeId}:${currentLanguage}`;
}

function createSummaryArea(notice) {
    const area = document.createElement("div");
    area.className = "notice-summary-area";

    const key = summaryKey(notice.id);
    const isOpen = openSummaries.has(notice.id);
    const isLoading = loadingSummaries.has(key);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "notice-summary-button";
    button.disabled = isLoading;
    button.textContent = isLoading
        ? t("notices.summarizing")
        : isOpen ? t("notices.hideSummary") : t("notices.summarize");
    button.addEventListener("click", () => toggleSummary(notice));
    area.appendChild(button);

    if (isOpen && noticeSummaries[key]) {
        const box = document.createElement("div");
        box.className = "notice-summary";

        const label = document.createElement("p");
        label.className = "notice-summary-label";
        label.textContent = t("notices.summaryLabel");

        const content = document.createElement("div");
        renderMarkdown(content, noticeSummaries[key]);

        box.append(label, content);
        area.appendChild(box);
    }

    return area;
}

async function toggleSummary(notice) {
    if (openSummaries.has(notice.id)) {
        openSummaries.delete(notice.id);
        renderNotices();
        return;
    }

    openSummaries.add(notice.id);
    const key = summaryKey(notice.id);

    if (noticeSummaries[key]) {
        renderNotices();
        return;
    }

    loadingSummaries.add(key);
    renderNotices();

    try {
        const data = await apiJson(
            `/notices/${notice.id}/summary?language=${encodeURIComponent(currentLanguage)}`,
            { method: "POST" },
            "notices.summaryFailed"
        );
        noticeSummaries[key] = data.summary;
    } catch (error) {
        console.error("Мэдэгдлийн тайлбар:", error);
        openSummaries.delete(notice.id);
        alert(error.message);
    } finally {
        loadingSummaries.delete(key);
        renderNotices();
    }
}

function renderNotices() {
    noticeList.replaceChildren();
    renderNoticeScope();
    const list = scopedNotices();

    if (!noticeStatus.dataset.busy) {
        noticeStatus.textContent = formatRefreshTime(noticesLastRefreshed);
    }

    if (list.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty-message";
        empty.textContent = t("notices.empty");
        noticeList.appendChild(empty);
        noticeMoreButton.hidden = true;
        return;
    }

    const visible = showAllNotices ? list : list.slice(0, NOTICE_VISIBLE_COUNT);
    visible.forEach(notice => noticeList.appendChild(createNoticeItem(notice)));

    noticeMoreButton.hidden = list.length <= NOTICE_VISIBLE_COUNT;
    noticeMoreButton.textContent = showAllNotices
        ? t("notices.showLess")
        : t("notices.showMore", { n: list.length - NOTICE_VISIBLE_COUNT });
}

async function refreshNotices({ quiet = false } = {}) {
    noticeRefreshButton.disabled = true;
    noticeStatus.dataset.busy = "1";
    noticeStatus.textContent = t("notices.refreshing");

    try {
        const result = await apiJson("/notices/refresh", { method: "POST" }, "notices.failed");
        delete noticeStatus.dataset.busy;

        await loadNotices();
        renderNotices();
        renderHome();

        if (!result.refreshed && !quiet) {
            noticeStatus.textContent = t("notices.cooldown", {
                n: Math.max(1, Math.ceil(result.retry_after / 60))
            });
        } else if (result.refreshed && result.new > 0) {
            noticeStatus.textContent = `${formatRefreshTime(noticesLastRefreshed)} · ${t("notices.newCount", { n: result.new })}`;
        }
    } catch (error) {
        delete noticeStatus.dataset.busy;
        console.error("Мэдэгдэл шинэчилж чадсангүй:", error);
        noticeStatus.textContent = t("notices.failed");
    } finally {
        noticeRefreshButton.disabled = false;
    }
}

// Нэвтэрсний дараа мэдэгдэл хуучирсан бол арын горимд шинэчилнэ.
function refreshNoticesIfStale() {
    if (hoursSince(noticesLastRefreshed) >= NOTICE_AUTO_REFRESH_HOURS) {
        refreshNotices({ quiet: true });
    }
}

noticeRefreshButton.addEventListener("click", () => refreshNotices());

noticeMoreButton.addEventListener("click", () => {
    showAllNotices = !showAllNotices;
    renderNotices();
});
