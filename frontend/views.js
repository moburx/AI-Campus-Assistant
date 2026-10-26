// ========================================
// AI Campus Assistant - Хэсэг солих, нүүр хуудас, AI цонх
// ========================================
// Хажуугийн цэсээр нэг удаад нэг хэсэг (view) харуулна.
// Хаяг (#assignments гэх мэт) өөрчлөгдөхөд тохирох хэсэг гарна,
// тиймээс браузерын "буцах" товч болон холбоос хуваалцах нь ажиллана.

const VIEWS = ["home", "assignments", "notices", "calendar", "courses", "stats"];
const VIEW_ALIASES = { dashboard: "home" };
const HOME_LIST_SIZE = 4;

const viewLinks = document.querySelectorAll("[data-view-link]");
const nextUpBody = document.getElementById("next-up-body");
const nextUpCard = document.getElementById("next-up");
const homeUpcoming = document.getElementById("home-upcoming");
const homeNotices = document.getElementById("home-notices");

const assistantPanel = document.getElementById("assistant");
const assistantOpenButton = document.getElementById("assistant-open");
const assistantCloseButton = document.getElementById("assistant-close");

// ---------- Хэсэг солих ----------
function viewFromHash() {
    const name = window.location.hash.slice(1);
    const view = VIEW_ALIASES[name] || name;
    return VIEWS.includes(view) ? view : "home";
}

function showView(view, { moveFocus = false } = {}) {
    document.querySelectorAll("[data-view]").forEach(section => {
        section.hidden = section.dataset.view !== view;
    });

    viewLinks.forEach(link => {
        if (link.dataset.viewLink === view) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });

    // Дэлгэц уншигч болон гараар ашиглагчид шинэ хэсгийн гарчиг руу шилжинэ.
    if (moveFocus) {
        const heading = document.querySelector(`[data-view="${view}"] h1, [data-view="${view}"] h2`);
        if (heading) {
            heading.tabIndex = -1;
            heading.focus({ preventScroll: true });
        }
        window.scrollTo(0, 0);
    }
}

function resetView() {
    if (window.location.hash) {
        history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    showView("home");
}

window.addEventListener("hashchange", () => showView(viewFromHash(), { moveFocus: true }));

// ---------- Нүүр хуудас ----------
// Солонгос оюутнуудын хэрэглэдэг "D-3" хэлбэр: 3 хоног үлдсэн.
function dDayText(isoDate) {
    const days = daysUntil(isoDate);
    if (Number.isNaN(days)) return "";
    if (days === 0) return "D-day";
    return days > 0 ? `D-${days}` : `D+${-days}`;
}

function upcomingAssignments() {
    return assignments
        .filter(item => !item.completed)
        .sort((a, b) => a.deadline.localeCompare(b.deadline) ||
            PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
}

function emptyListItem(key) {
    const item = document.createElement("li");
    item.className = "empty-message";
    item.textContent = t(key);
    return item;
}

function renderNextUp(next) {
    nextUpBody.replaceChildren();
    nextUpCard.className = "next-up";

    if (!next) {
        nextUpCard.classList.add("is-empty");

        const text = document.createElement("p");
        text.className = "next-up-empty";
        text.textContent = t("home.nextUpEmpty");

        const link = document.createElement("a");
        link.className = "button-link";
        link.href = "#assignments";
        link.textContent = t("welcome.start");

        nextUpBody.append(text, link);
        return;
    }

    nextUpCard.classList.add(dueState(next));

    const count = document.createElement("strong");
    count.className = "next-up-dday";
    count.textContent = dDayText(next.deadline);

    const info = document.createElement("div");
    info.className = "next-up-info";

    const title = document.createElement("h2");
    title.className = "next-up-title";
    title.textContent = next.title;

    const meta = document.createElement("p");
    meta.className = "next-up-meta";
    meta.append(
        createCourseChip(next.course, next.course_color),
        document.createTextNode(`${formatDate(next.deadline)} · ${dueLabel(next)}`)
    );

    info.append(title, meta);
    nextUpBody.append(count, info);
}

function renderHomeUpcoming(list) {
    homeUpcoming.replaceChildren();

    if (list.length === 0) {
        homeUpcoming.appendChild(emptyListItem("home.noUpcoming"));
        return;
    }

    list.slice(0, HOME_LIST_SIZE).forEach(item => {
        const row = document.createElement("li");
        row.className = `home-row ${dueState(item)}`;

        const badge = document.createElement("span");
        badge.className = "home-dday";
        badge.textContent = dDayText(item.deadline);

        const text = document.createElement("div");
        text.className = "home-row-text";

        const title = document.createElement("strong");
        title.textContent = item.title;

        text.append(title, createCourseChip(item.course, item.course_color));
        row.append(badge, text);
        homeUpcoming.appendChild(row);
    });
}

function renderHomeNotices() {
    homeNotices.replaceChildren();

    if (schoolNotices.length === 0) {
        homeNotices.appendChild(emptyListItem("notices.empty"));
        return;
    }

    schoolNotices.slice(0, HOME_LIST_SIZE).forEach(notice => {
        const row = document.createElement("li");
        row.className = "home-row";

        const date = document.createElement("span");
        date.className = "home-date";
        date.textContent = formatDate(notice.posted_at, { month: "short", day: "numeric" });

        const link = document.createElement("a");
        link.className = "home-notice-link";
        link.href = notice.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = notice.title;

        row.append(date, link);
        homeNotices.appendChild(row);
    });
}

function renderHome() {
    const upcoming = upcomingAssignments();
    renderNextUp(upcoming[0]);
    renderHomeUpcoming(upcoming);
    renderHomeNotices();
}

// ---------- AI туслахын цонх ----------
// iPhone дээр keyboard гарахад дэлгэцийн харагдах хэсэг (visual viewport) багасдаг.
// Цонхыг тэр хэмжээнд тааруулахгүй бол дээд хэсэг (✕ товч) дэлгэцээс гарна.
function fitAssistantToViewport() {
    const viewport = window.visualViewport;
    if (!viewport || assistantPanel.hidden) return;

    assistantPanel.style.setProperty("--viewport-height", `${viewport.height}px`);
    assistantPanel.style.setProperty("--viewport-top", `${viewport.offsetTop}px`);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", fitAssistantToViewport);
    window.visualViewport.addEventListener("scroll", fitAssistantToViewport);
}

function openAssistant() {
    assistantPanel.hidden = false;
    assistantOpenButton.setAttribute("aria-expanded", "true");
    document.body.classList.add("assistant-open");
    fitAssistantToViewport();
    chatInput.focus();
}

function closeAssistant({ restoreFocus = true } = {}) {
    if (assistantPanel.hidden) return;

    assistantPanel.hidden = true;
    assistantOpenButton.setAttribute("aria-expanded", "false");
    document.body.classList.remove("assistant-open");

    if (restoreFocus) {
        assistantOpenButton.focus();
    }
}

assistantOpenButton.addEventListener("click", () => {
    if (assistantPanel.hidden) {
        openAssistant();
    } else {
        closeAssistant();
    }
});

assistantCloseButton.addEventListener("click", () => closeAssistant());

document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !assistantPanel.hidden && !editDialog.open) {
        closeAssistant();
    }
});

showView(viewFromHash());
