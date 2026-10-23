// ========================================
// AI Campus Assistant - 학교 공지 (сургуулийн мэдэгдэл)
// ========================================
// Сервер сургуулийн самбараас татсан мэдэгдлүүдийг харуулна.
// Шинэчлэх товч нь серверт 10 минутад нэг удаа л зөвшөөрөгдөнө.

const NOTICE_NEW_DAYS = 3;          // сүүлийн 3 хоногийн мэдэгдэлд "NEW" тэмдэг
const NOTICE_AUTO_REFRESH_HOURS = 6; // үүнээс хуучин бол нэвтрэхэд автоматаар шинэчилнэ
const NOTICE_VISIBLE_COUNT = 8;      // эхэндээ харуулах тоо ("Дэлгэрэнгүй" дарвал бүгд)

let schoolNotices = [];
let noticesLastRefreshed = null;
let showAllNotices = false;

const noticeList = document.getElementById("notice-list");
const noticeStatus = document.getElementById("notices-status");
const noticeRefreshButton = document.getElementById("notices-refresh");
const noticeMoreButton = document.getElementById("notices-more");

async function loadNotices() {
    const data = await apiJson("/notices?limit=30", {}, "notices.failed");
    schoolNotices = data.notices;
    noticesLastRefreshed = data.last_refreshed;
}

function resetNotices() {
    schoolNotices = [];
    noticesLastRefreshed = null;
    showAllNotices = false;
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

    item.append(meta, link);
    return item;
}

function renderNotices() {
    noticeList.replaceChildren();

    if (!noticeStatus.dataset.busy) {
        noticeStatus.textContent = formatRefreshTime(noticesLastRefreshed);
    }

    if (schoolNotices.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty-message";
        empty.textContent = t("notices.empty");
        noticeList.appendChild(empty);
        noticeMoreButton.hidden = true;
        return;
    }

    const visible = showAllNotices ? schoolNotices : schoolNotices.slice(0, NOTICE_VISIBLE_COUNT);
    visible.forEach(notice => noticeList.appendChild(createNoticeItem(notice)));

    noticeMoreButton.hidden = schoolNotices.length <= NOTICE_VISIBLE_COUNT;
    noticeMoreButton.textContent = showAllNotices
        ? t("notices.showLess")
        : t("notices.showMore", { n: schoolNotices.length - NOTICE_VISIBLE_COUNT });
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
