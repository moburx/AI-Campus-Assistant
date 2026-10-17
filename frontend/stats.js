// ========================================
// AI Campus Assistant - Самбар ба статистик
// ========================================
// /api/stats-ээс авсан өгөгдлөөр тоон хавтан, баганан график,
// хичээл тус бүрийн явцыг зурна. График бүрийг хүснэгтээр ч харж болно.

let statsData = null;
let showStatsTable = false;

const PRIORITY_COLORS = {
    high: "#3730a3",
    medium: "#6366f1",
    low: "#a5b4fc"
};

const statsMessage = document.getElementById("stats-message");
const statsTableToggle = document.getElementById("stats-table-toggle");

// Бүх графикт нэг tooltip ашиглана.
const chartTooltip = document.createElement("div");
chartTooltip.className = "chart-tooltip";
chartTooltip.setAttribute("role", "tooltip");
chartTooltip.hidden = true;
document.body.appendChild(chartTooltip);

async function loadStats() {
    try {
        statsData = await apiJson("/stats", {}, "stats.loadFailed");
        statsMessage.textContent = "";
    } catch (error) {
        statsData = null;
        statsMessage.textContent = error.message;
    }
}

function resetStats() {
    statsData = null;
    statsMessage.textContent = "";
}

function setText(id, value) {
    document.getElementById(id).textContent = value;
}

function renderTiles() {
    const data = statsData || {
        total: 0,
        completed: 0,
        remaining: 0,
        overdue: 0,
        due_this_week: 0,
        completion_rate: 0
    };

    // Нүүр хэсгийн самбар
    setText("tile-remaining", data.remaining);
    setText("tile-due-week", data.due_this_week);
    setText("tile-overdue", data.overdue);
    setText("tile-rate", `${data.completion_rate}%`);

    // Статистик хэсэг
    setText("stats-total", data.total);
    setText("stats-completed", data.completed);
    setText("stats-overdue", data.overdue);
    setText("stats-rate", `${data.completion_rate}%`);

    document.querySelectorAll(".tile-warning").forEach(tile => {
        tile.classList.toggle("is-active", data.overdue > 0);
    });
}

// ---------- Tooltip ----------
function showTooltip(target, text) {
    chartTooltip.textContent = text;
    chartTooltip.hidden = false;

    const rect = target.getBoundingClientRect();
    const tipRect = chartTooltip.getBoundingClientRect();
    const left = Math.min(
        Math.max(8, rect.left + rect.width / 2 - tipRect.width / 2),
        window.innerWidth - tipRect.width - 8
    );

    chartTooltip.style.left = `${left + window.scrollX}px`;
    chartTooltip.style.top = `${rect.top + window.scrollY - tipRect.height - 8}px`;
}

function hideTooltip() {
    chartTooltip.hidden = true;
}

// ---------- Баганан график ----------
// points: [{ label, fullLabel, value }]
function renderBarChart(container, points) {
    container.replaceChildren();

    const max = Math.max(1, ...points.map(point => point.value));
    const hasData = points.some(point => point.value > 0);

    const plot = document.createElement("div");
    plot.className = "bar-plot";

    points.forEach(point => {
        const column = document.createElement("div");
        column.className = "bar-column";
        column.tabIndex = 0;

        const description = `${point.fullLabel}: ${t("stats.items", { n: point.value })}`;
        column.setAttribute("aria-label", description);

        const value = document.createElement("span");
        value.className = "bar-value";
        value.textContent = point.value > 0 ? point.value : "";

        const bar = document.createElement("div");
        bar.className = "bar";
        bar.style.height = `${(point.value / max) * 100}%`;

        const label = document.createElement("span");
        label.className = "bar-label";
        label.textContent = point.label;

        column.append(value, bar, label);

        column.addEventListener("mouseenter", () => showTooltip(bar, description));
        column.addEventListener("focus", () => showTooltip(bar, description));
        column.addEventListener("mouseleave", hideTooltip);
        column.addEventListener("blur", hideTooltip);

        plot.appendChild(column);
    });

    container.appendChild(plot);

    if (!hasData) {
        const empty = document.createElement("p");
        empty.className = "chart-empty";
        empty.textContent = t("stats.noData");
        container.appendChild(empty);
    }
}

function renderDataTable(table, points) {
    table.replaceChildren();

    const head = table.createTHead().insertRow();
    [t("stats.colPeriod"), t("stats.colCount")].forEach(text => {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = text;
        head.appendChild(cell);
    });

    const body = table.createTBody();
    points.forEach(point => {
        const row = body.insertRow();
        row.insertCell().textContent = point.fullLabel;
        row.insertCell().textContent = point.value;
    });
}

function weeklyPoints() {
    const weeks = statsData ? statsData.weekly_completed : [];

    return weeks.map(week => ({
        label: formatDate(week.week_start, { month: "numeric", day: "numeric" }),
        fullLabel: t("stats.weekOf", {
            date: formatDate(week.week_start, { year: "numeric", month: "long", day: "numeric" })
        }),
        value: week.count
    }));
}

function upcomingPoints() {
    const days = statsData ? statsData.upcoming : [];

    return days.map(day => ({
        label: formatDate(day.date, { weekday: "short" }),
        fullLabel: formatDate(day.date, { month: "long", day: "numeric", weekday: "long" }),
        value: day.count
    }));
}

// ---------- Явцын жагсаалт ----------
// rows: [{ name, color, done, total }]
function renderProgressList(list, rows) {
    list.replaceChildren();

    if (rows.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty-message";
        empty.textContent = t("stats.noData");
        list.appendChild(empty);
        return;
    }

    rows.forEach(row => {
        const item = document.createElement("li");
        item.className = "progress-row";

        const header = document.createElement("div");
        header.className = "progress-header";

        const name = document.createElement("span");
        name.className = "course-chip";

        const dot = document.createElement("span");
        dot.className = "course-dot";
        dot.style.backgroundColor = row.color;
        name.append(dot, document.createTextNode(row.name));

        const count = document.createElement("span");
        count.className = "progress-count";
        const percent = row.total ? Math.round((row.done / row.total) * 100) : 0;
        count.textContent = `${t("courses.count", { done: row.done, total: row.total })} · ${percent}%`;

        header.append(name, count);
        item.append(header, createProgressBar(row.done, row.total, row.color));
        list.appendChild(item);
    });
}

function courseRows() {
    const items = statsData ? statsData.by_course : [];

    return items.map(course => ({
        name: course.name,
        color: course.color,
        done: course.completed,
        total: course.total
    }));
}

function priorityRows() {
    if (!statsData) return [];

    return ["high", "medium", "low"]
        .map(priority => ({
            name: t(`priority.${priority}`),
            color: PRIORITY_COLORS[priority],
            done: statsData.by_priority[priority].completed,
            total: statsData.by_priority[priority].total
        }))
        .filter(row => row.total > 0);
}

function renderStats() {
    renderTiles();

    const weekly = weeklyPoints();
    const upcoming = upcomingPoints();

    renderBarChart(document.getElementById("chart-weekly"), weekly);
    renderBarChart(document.getElementById("chart-upcoming"), upcoming);
    renderDataTable(document.getElementById("table-weekly"), weekly);
    renderDataTable(document.getElementById("table-upcoming"), upcoming);

    renderProgressList(document.getElementById("chart-courses"), courseRows());
    renderProgressList(document.getElementById("chart-priority"), priorityRows());

    applyStatsView();
}

// График ↔ хүснэгт солих
function applyStatsView() {
    document.getElementById("chart-weekly").hidden = showStatsTable;
    document.getElementById("chart-upcoming").hidden = showStatsTable;
    document.getElementById("table-weekly").hidden = !showStatsTable;
    document.getElementById("table-upcoming").hidden = !showStatsTable;

    statsTableToggle.dataset.i18n = showStatsTable ? "stats.hideTable" : "stats.showTable";
    statsTableToggle.textContent = t(statsTableToggle.dataset.i18n);
    statsTableToggle.setAttribute("aria-pressed", String(showStatsTable));
}

statsTableToggle.addEventListener("click", () => {
    showStatsTable = !showStatsTable;
    hideTooltip();
    applyStatsView();
});

window.addEventListener("scroll", hideTooltip, { passive: true });
